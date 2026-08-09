# DECISIONS

Five engineering tradeoffs, why I made them, and what I'd do with two more weeks.

---

## 1. Gemini rate limits, retries, and concurrency

**Decision.** One Gemini call per email with `temperature=0` and
`response_mime_type=application/json`. Each call retries up to 3× on any transient error
with exponential backoff **plus jitter** (`2^attempt + rand(0,0.5)s`). In `/ingest`,
classification runs on a **thread pool capped at `GEMINI_MAX_CONCURRENCY` (default 5)**,
so a 100-email batch never fires 100 concurrent calls and trips the free-tier rate limit.
Crucially, **classification (stages 1–5) runs concurrently, but DB writes (stage 6) run
sequentially in `received_at` order** — that keeps thread reconciliation correct (an
original always lands before its reply) while still parallelising the slow part.

**Why.** The free tier is generous but not unlimited, and grading posts batches minutes
apart. Jitter avoids the thundering-herd retry pattern where all 5 workers back off in
lockstep. Capping concurrency is cheaper and more predictable than discovering the limit
at 429 time.

**Two more weeks.** A token-bucket limiter shared across requests (not just per-batch), a
small response cache keyed on `hash(cleaned_body)` for near-duplicate emails, and batching
several emails into one structured call to cut request count ~5×.

## 2. Idempotency — three layers, not one

**Decision.** Duplicates are prevented at three points:
- a **unique constraint** on `(candidate_id, source_email_id)` in Postgres — the hard floor;
- a **replay check** in the pipeline: if a task already exists for this exact
  `source_email_id`, return it untouched and count it as *neither* created nor updated;
- a **thread lookup**: if a task exists for this `thread_id`, the email takes the PATCH
  path (update + a `task_revisions` diff row), never a second create.

`POST /tasks` itself dedups too — re-posting the same `source_email_id` returns the
existing task with 200 instead of a duplicate.

**Why.** The brief tests idempotency (Run 2) and thread reconciliation (Run 3) directly,
and explicitly warns the Task API has *no* uniqueness guarantee unless you build it. One
layer isn't enough: the unique constraint stops the DB-level dup, but the replay/thread
logic is what makes the *counts* (`tasks_created`/`tasks_updated`) correct, which is what
Runs 2 and 3 actually check.

**Two more weeks.** Wrap each email's write in a savepoint so a mid-batch failure can't
partially double-count, and add an idempotency-key header on `/ingest` so a retried whole
batch is a guaranteed no-op.

## 3. Data model designed so chat never re-hits Gemini for facts

**Decision.** Three tables. `tasks` is the raw Task API store. **`email_records`** is the
real workhorse: one row per email *ever processed, including skipped ones*, carrying
`decision`, `category`, `assignee_id`, `confidence`, `reasoning`, `rules_fired`,
`skip_reason`, `is_spurious`, `run_id`, latency and token counts. **`task_revisions`** is
append-only history. Every `/ingest` stamps a `run_id` on every row it touches.

**Why.** The Task API has no concept of "skipped" — but proving the negatives (this
newsletter was *seen and correctly ignored*) is the whole point of reducing the ops
queue. Storing the decision and its reasoning at write time means the chat and
`/api/stats` answer from stored ground truth: counts, group-bys, spurious rate, and "was
this thread updated twice?" are all a `SELECT`, never another model call. That also makes
answers **stable** — the same question twice hits the same rows.

**Two more weeks.** Materialised per-run aggregate rows so `/api/stats` is O(1) instead of
scanning `email_records`, and a proper migrations tool (Alembic) instead of `create_all`.

## 4. Chat grounding — the exact path that prevents hallucinated numbers

**Decision.** The chat is an **intent router**, not a free-form LLM:

```
question
  → Gemini call #1 returns ONLY a query plan  {intent, filters, scope}   (no numbers)
  → our code runs the matching parameterised query over email_records/tasks/revisions
  → Gemini call #2 phrases the rows we computed  (told: use only these numbers, say zero plainly)
  → { answer, supporting_data (the literal query result), query (the plan) }
```

Supported intents: `count_by_category`, `count_by_assignee`, `count_skipped_by_reason`,
`list_triage_with_reasons`, `spurious_rate`, `compound_filter`, `sum_deal_value`
(reports null-count separately, never treats null as 0), `threads_updated_multiple_times`,
`action_request` (declines), `unknown` (honest "I don't store that"). The model **never
writes SQL** and **never emits a figure**; if Gemini is unavailable, a keyword planner
produces the same plan and a template phrases it, so chat still works and stays grounded.

**Why.** A chat that invents a plausible count is worse than no chat — the brief says so
and tests it (the GST-refund zero trap, the out-of-scope "send an email" trap, and asking
the same question twice). Separating *planning* from *computation* from *phrasing* means
the number is always traceable to a query result, zero is a first-class answer, and
determinism is structural, not hoped-for.

**Two more weeks.** A confirmation step that echoes the parsed plan for ambiguous
questions, and support for follow-up context ("and how many of those are high priority?").

## 5. What the system gets wrong that I shipped anyway

**Company-name recall vs. precision, and the under-confident fallback.**

I refuse to infer `company_name` from an email domain unless it unambiguously *is* the
company name. This is deliberate — the brief penalises fabricated fields harder than
nulls — but it means a company named only in the sender domain comes back `null`. I
shipped the precision-first behaviour knowing it costs recall.

Relatedly, when Gemini fails and the rules-only fallback takes over, it emits a flat low
confidence (≤ 0.35). So during an LLM outage the confidence score stops being a useful
ranking signal — it's honestly-low rather than fabricated-informative (see EVALS §
calibration). I chose "an email routed under-confidently" over "an email dropped," because
a slow or hedged answer beats a lost RFP. The fix I'd prioritise with more time is a
richer deterministic scorer that produces a genuine confidence spread from signal
strength (how many rules fired, how clean the category match was) rather than a constant.

---

### On splitting ambiguous emails (from §6, Example 11)

I route two-owner emails to `u_triage` with confidence < 0.55 and both asks in the
description, rather than splitting into two tasks. Splitting is a defensible alternative,
but it risks double-counting a single opportunity and creating orphaned half-tasks; a
single triage item with a human in the loop is the safer default for an ops queue whose
whole purpose is to *shrink*, not fragment.

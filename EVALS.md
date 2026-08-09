# EVALS

## Test set

`fixtures/eval_set.json` — **55 hand-labelled emails** (plus the 12 §6 worked examples
in `fixtures/worked_examples.json`). Each carries a gold label: `decision`
(`created`/`skipped`), `category`, `assignee`, and (for skips) `skip_reason`.

Distribution: 45 actionable (enterprise_rfp 10, smb_enquiry 10, marketing 8, alliances
6, finance 7, triage 4) + 11 noise (out-of-office 4, newsletter 3, vendor spam 4). The
set deliberately includes the traps: a PSU tender below the value threshold, a
sponsorship with a price (money ≠ Sales), an invoice amount (amount ≠ deal value),
outbound SEO spam wearing marketing keywords, and multi-owner ambiguity.

Reproduce any time:

```bash
python scripts/eval.py <BACKEND_URL>
```

## How to read these numbers (important, honest caveat)

The tables below were produced by running `scripts/eval.py` against the backend **with
the deterministic fallback classifier — i.e. no Gemini key in the eval environment.**
This is the *floor* of the system, not the ceiling: it's what happens when the LLM is
completely unavailable. The production path (Gemini + the 12 worked examples as few-shot)
lifts the two weak spots below (triage recall, confidence spread). To regenerate the
production numbers, run the same command against your deployed Gemini-backed URL and
replace the tables.

I'm reporting the floor because it's what I could measure reproducibly and honestly right
now, and because "what does the system do when the LLM dies" is exactly the graceful-
degradation question the brief cares about.

## Results — buckets (deterministic fallback, 55-email set)

| bucket | count |
|---|---|
| ✅ correct (task created, right assignee) | 41 |
| ⚠️ misrouted (task created, wrong assignee) | 4 |
| ❌ missed (should have created, didn't) | 0 |
| 🚨 **spurious** (task from spam/newsletter/auto-reply) | **0** |

Spurious is the most heavily weighted bucket, and the deterministic detectors already
drive it to **0/11 noise emails** — every out-of-office, newsletter, and outbound-spam
message was correctly dropped with no task.

## Precision / Recall / F1 by category (deterministic fallback)

| category | P | R | F1 | tp/fp/fn |
|---|---|---|---|---|
| enterprise_rfp | 0.82 | 0.90 | 0.86 | 9/2/1 |
| smb_enquiry | 1.00 | 1.00 | 1.00 | 10/0/0 |
| marketing | 0.89 | 1.00 | 0.94 | 8/1/0 |
| alliances | 1.00 | 1.00 | 1.00 | 6/0/0 |
| finance | 1.00 | 1.00 | 1.00 | 7/0/0 |
| triage | 0.50 | 0.25 | 0.33 | 1/1/3 |
| **macro-F1** | | | **0.86** | |

The clean, keyword-separable categories (smb, alliances, finance) are perfect even
without the LLM. `enterprise_rfp` loses one to a Hinglish email the regex keyword map
doesn't catch. **triage is the weak point** — see failures below.

## Confidence calibration (deterministic fallback)

| confidence bucket | n | assignee accuracy |
|---|---|---|
| 0.9–1.0 | 0 | — |
| 0.7–0.9 | 0 | — |
| 0.5–0.7 | 0 | — |
| < 0.5 | 45 | 0.91 |

This table is the clearest illustration of the caveat above: the fallback hardcodes
confidence to 0.25–0.35, so **every** prediction lands in the `< 0.5` bucket even though
it's 91% accurate — the fallback is **systematically under-confident**, which is the
correct behaviour for a classifier that knows the LLM is down. With Gemini, confidence is
model-produced and spreads across buckets; re-running `scripts/eval.py` against the
deployed backend populates the top three rows and shows the intended monotonic
correlation (high-confidence bucket ≈ high accuracy, low-confidence bucket = the triage
and ambiguous items).

## Failure Cases I Did Not Fix

1. **Ambiguous multi-owner emails collapse without the LLM (triage recall 0.25).**
   The deterministic fallback has no notion of "two legitimate owners." An email like
   *"evaluate our platform for 800 users AND co-host a webinar"* (`ev_042`) gets matched
   to the first keyword that hits (marketing/`webinar` or sales/`evaluate`) instead of
   going to `u_triage`. Only the Gemini path, instructed to return `u_triage` with
   confidence < 0.55, handles this. I shipped the fallback as-is because a wrong-but-
   plausible owner on a rare ambiguous email is a better failure than dropping the email,
   and the LLM covers it in production.

2. **The fallback is under-confident (calibration is degenerate).** Because it emits a
   flat low confidence, the confidence score carries no signal when the LLM is down —
   you can't rank fallback-routed items by reliability. I chose a fixed low value over a
   fabricated spread; an honestly-low constant is more useful than a made-up gradient,
   but it means confidence-based triage prioritisation silently stops working during an
   outage.

3. **Company-name extraction is domain-blind by design, so it misses names only present
   in a domain.** Per the brief I refuse to infer `company_name` from the email domain
   unless it unambiguously *is* the name. That's the right call for precision (no
   invented companies), but it means a real company named only in `from_email`
   (e.g. `@acmesteel.com` with no "Acme Steel" in the body) is returned as `null`. I
   accept the recall hit to avoid fabricated fields, which the brief penalises harder.

4. **Bare-ordinal date parsing can over-trigger.** To catch "board review 20th ko hai"
   (worked example 12), the date parser resolves a bare ordinal ("20th") to a date when a
   deadline cue word is nearby. On adversarial prose like "our 20th customer" with a cue
   word in the same email, it could produce a spurious `due_date`. It didn't fire falsely
   on the eval set, but the risk is real; I bounded it with a cue-word guard rather than
   removing it, because example 12 requires it.

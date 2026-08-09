import { useState } from "react";
import type { ProcessedItem } from "../types";

interface Props {
  items: ProcessedItem[];
  names: Record<string, string>;
  /** When set, show only the first N rows with a "Show all processed" toggle. */
  initialLimit?: number;
}

function initials(name?: string, fallback = "?") {
  if (!name) return fallback;
  const parts = name.split(" ").filter(Boolean);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || fallback;
}

function nullable(v: unknown) {
  if (v === null || v === undefined || v === "") return <span className="null-tag">null</span>;
  if (typeof v === "number") return v.toLocaleString("en-IN");
  return String(v);
}

function Row({ item, names }: { item: ProcessedItem; names: Record<string, string> }) {
  const [open, setOpen] = useState(false);
  const t = item.task;
  const assignee = item.assignee_id || t?.assignee_id || null;
  const name = assignee ? names[assignee] : undefined;
  const override =
    item.llm_proposed_assignee && assignee && item.llm_proposed_assignee !== assignee;

  return (
    <div className={`result-row ${item.decision}`}>
      <div className="result-head" onClick={() => setOpen((o) => !o)}>
        <span className="chevron">{open ? "▾" : "▸"}</span>
        {item.decision === "skipped" ? (
          <span className="avatar" style={{ background: "var(--surface-2)", color: "var(--text-muted)" }}>—</span>
        ) : (
          <span className="avatar">{initials(name, assignee?.replace("u_", "").slice(0, 2).toUpperCase())}</span>
        )}
        <span className="result-title">{item.subject || item.task?.title || item.email_id}</span>
        <div className="result-meta">
          {item.category && <span className="chip">{item.category}</span>}
          {t && <span className={`badge ${t.priority}`}>{t.priority}</span>}
          {item.confidence != null && <span className="conf">conf {item.confidence.toFixed(2)}</span>}
          <span className={`badge ${item.decision}`}>{item.decision}</span>
        </div>
      </div>

      {open && (
        <div className="result-detail">
          {item.skip_reason && (
            <div className="chips-row">
              <span className="chip">skip reason: {item.skip_reason}</span>
              <span className="chip">direction: {item.direction_of_intent}</span>
            </div>
          )}

          {item.rules_fired?.length > 0 && (
            <div className="chips-row">
              {item.rules_fired.map((r) => (
                <span key={r} className="chip rule">{r}</span>
              ))}
            </div>
          )}

          {override && (
            <div className="override-note">
              Model proposed <b>{names[item.llm_proposed_assignee!] || item.llm_proposed_assignee}</b>, a
              deterministic rule overrode it to <b>{name || assignee}</b>.
            </div>
          )}
          {!override && item.llm_proposed_assignee && item.decision !== "skipped" && (
            <div className="diff-line">
              model proposed {item.llm_proposed_assignee} · assigned {assignee} (agreed)
            </div>
          )}

          {item.reasoning && <div className="reasoning">“{item.reasoning}”</div>}

          <div className="detail-grid">
            <span className="k">assignee</span><span>{nullable(assignee ? `${assignee}${name ? ` (${name})` : ""}` : null)}</span>
            <span className="k">category</span><span>{nullable(item.category)}</span>
            <span className="k">priority</span><span>{nullable(t?.priority)}</span>
            <span className="k">due_date</span><span>{nullable(t?.due_date)}</span>
            <span className="k">deal_value_inr</span><span>{t?.deal_value_inr == null ? <span className="null-tag">null</span> : `₹${t.deal_value_inr.toLocaleString("en-IN")}`}</span>
            <span className="k">company_name</span><span>{nullable(t?.company_name)}</span>
            <span className="k">source_email_id</span><span className="mono">{item.email_id}</span>
            <span className="k">thread_id</span><span className="mono">{item.thread_id}</span>
            {t && <><span className="k">task_id</span><span className="mono">{t.task_id}</span></>}
            {item.latency_ms != null && <><span className="k">latency</span><span className="mono">{item.latency_ms} ms{item.token_count ? ` · ${item.token_count} tok` : ""}</span></>}
          </div>

          {item.revisions.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="k" style={{ color: "var(--text-secondary)", fontSize: 12, marginBottom: 4 }}>
                revisions ({item.revision_count})
              </div>
              {item.revisions.map((rev) =>
                Object.entries(rev.changed_fields).map(([field, d]) => (
                  <div key={`${rev.revision_index}-${field}`} className="diff-line">
                    #{rev.revision_index} {field}: {String(d.from ?? "null")} <span className="to">→ {String(d.to ?? "null")}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Results({ items, names, initialLimit }: Props) {
  const [showAll, setShowAll] = useState(false);
  const capped = initialLimit != null && !showAll;
  const visible = capped ? items.slice(0, initialLimit) : items;

  return (
    <section className="card section" id="results">
      <div className="section-head">
        <span className="section-title">3 · results with decision trace</span>
        <span className="section-sub">
          {items.length > 0
            ? `showing ${visible.length} of ${items.length} processed · skipped shown greyed`
            : "waiting for a batch"}
        </span>
      </div>
      {items.length === 0 ? (
        <div className="loading">Route a batch above to see one row per email — assignee, rules fired, model-vs-final, reasoning, and extracted fields.</div>
      ) : (
        visible.map((it) => <Row key={it.email_id} item={it} names={names} />)
      )}

      {initialLimit != null && items.length > initialLimit && (
        <div style={{ marginTop: 14, textAlign: "center" }}>
          <button className="btn btn-outline btn-sm" onClick={() => setShowAll((s) => !s)}>
            {showAll ? "Show fewer" : `Show all processed (${items.length})`}
          </button>
        </div>
      )}
    </section>
  );
}

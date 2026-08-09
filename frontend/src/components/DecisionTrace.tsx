import type { ProcessedItem } from "../types";

// Full (non-collapsible) decision trace for a single processed email.
export default function DecisionTrace({
  item,
  names,
}: {
  item: ProcessedItem;
  names: Record<string, string>;
}) {
  const t = item.task;
  const assignee = item.assignee_id || t?.assignee_id || null;
  const name = assignee ? names[assignee] : undefined;
  const override = item.llm_proposed_assignee && assignee && item.llm_proposed_assignee !== assignee;

  const nullable = (v: unknown) =>
    v === null || v === undefined || v === "" ? <span className="null-tag">null</span>
      : typeof v === "number" ? v.toLocaleString("en-IN") : String(v);

  return (
    <div className="trace-card">
      <div className="trace-top">
        <span className={`badge ${item.decision}`}>{item.decision}</span>
        {item.category && <span className="chip">{item.category}</span>}
        {t && <span className={`badge ${t.priority}`}>{t.priority}</span>}
        {item.confidence != null && <span className="conf">confidence {item.confidence.toFixed(2)}</span>}
        {assignee && item.decision !== "skipped" && (
          <span className="chip">→ {name || assignee}</span>
        )}
      </div>

      {item.skip_reason && (
        <div className="chips-row">
          <span className="chip">skip reason: {item.skip_reason}</span>
          <span className="chip">direction: {item.direction_of_intent}</span>
        </div>
      )}

      {item.rules_fired?.length > 0 && (
        <div className="chips-row">
          {item.rules_fired.map((r) => <span key={r} className="chip rule">{r}</span>)}
        </div>
      )}

      {override && (
        <div className="override-note">
          Model proposed <b>{names[item.llm_proposed_assignee!] || item.llm_proposed_assignee}</b> —
          a deterministic rule overrode it to <b>{name || assignee}</b>.
        </div>
      )}
      {!override && item.llm_proposed_assignee && item.decision !== "skipped" && (
        <div className="diff-line">model proposed {item.llm_proposed_assignee} · final {assignee} (agreed)</div>
      )}

      {item.reasoning && <div className="reasoning">“{item.reasoning}”</div>}

      <div className="detail-grid">
        <span className="k">intent / category</span><span>{nullable(item.category)}</span>
        <span className="k">assignee</span><span>{nullable(assignee ? `${assignee}${name ? ` (${name})` : ""}` : null)}</span>
        <span className="k">priority</span><span>{nullable(t?.priority)}</span>
        <span className="k">confidence</span><span>{item.confidence != null ? item.confidence.toFixed(2) : <span className="null-tag">null</span>}</span>
        <span className="k">due_date</span><span>{nullable(t?.due_date)}</span>
        <span className="k">deal_value_inr</span><span>{t?.deal_value_inr == null ? <span className="null-tag">null</span> : `₹${t.deal_value_inr.toLocaleString("en-IN")}`}</span>
        <span className="k">company_name</span><span>{nullable(t?.company_name)}</span>
        <span className="k">model proposal</span><span>{nullable(item.llm_proposed_assignee)}</span>
        <span className="k">final decision</span><span>{item.decision}{item.task_id ? ` · ${item.task_id}` : ""}</span>
        <span className="k">task action</span><span>{item.task_id ? `task ${item.decision}` : "no task created"}</span>
        {item.latency_ms != null && <><span className="k">latency</span><span className="mono">{item.latency_ms} ms{item.token_count ? ` · ${item.token_count} tok` : ""}</span></>}
      </div>

      {item.revisions.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div className="k" style={{ fontSize: 12, marginBottom: 4 }}>revisions ({item.revision_count})</div>
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
  );
}

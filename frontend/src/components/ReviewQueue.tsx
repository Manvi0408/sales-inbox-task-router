import type { ProcessedItem } from "../types";
import DecisionTrace from "./DecisionTrace";

// Items a human should review: routed to triage, or created with low confidence.
export default function ReviewQueue({
  items,
  names,
}: {
  items: ProcessedItem[];
  names: Record<string, string>;
}) {
  const review = items.filter(
    (i) =>
      i.task &&
      (i.assignee_id === "u_triage" || i.category === "triage" || (i.confidence != null && i.confidence < 0.5))
  );

  return (
    <div>
      <div className="page-head">
        <h2 className="page-title">Review Queue</h2>
        <p className="page-sub">Triage items and low-confidence routes flagged for a human — confidently-wrong is the failure we avoid.</p>
      </div>

      {review.length === 0 ? (
        <div className="card"><div className="loading">Nothing needs review. Triage and low-confidence tasks show up here after routing.</div></div>
      ) : (
        review.map((it) => (
          <div key={it.email_id} className="card section">
            <div className="section-head">
              <span className="section-title">{it.subject || it.email_id}</span>
              <span className="section-sub">{it.from_email}</span>
            </div>
            <DecisionTrace item={it} names={names} />
          </div>
        ))
      )}
    </div>
  );
}

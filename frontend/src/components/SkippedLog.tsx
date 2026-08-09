import type { ProcessedItem } from "../types";

// Emails that were processed but skipped (no task created). Real persisted data.
export default function SkippedLog({ items }: { items: ProcessedItem[] }) {
  const skipped = items.filter((i) => i.decision === "skipped");

  return (
    <div>
      <div className="page-head">
        <h2 className="page-title">Skipped Noise Log</h2>
        <p className="page-sub">Emails the router saw and correctly ignored — proving the negatives, not hiding them.</p>
      </div>

      <div className="card">
        <div className="section-head">
          <span className="section-title">{skipped.length} skipped</span>
          <span className="section-sub">no task created for any of these</span>
        </div>
        {skipped.length === 0 ? (
          <div className="loading">No skipped emails yet. Route a batch (Inbox Ingest &amp; Triage) to populate this.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Sender</th>
                  <th>Reason</th>
                  <th>Direction</th>
                  <th>Confidence</th>
                  <th>Task created</th>
                </tr>
              </thead>
              <tbody>
                {skipped.map((s) => (
                  <tr key={s.email_id}>
                    <td>{s.subject || "—"}</td>
                    <td className="mono">{s.from_email || s.from_name || "—"}</td>
                    <td><span className="chip">{s.skip_reason || "other"}</span></td>
                    <td className="muted">{s.direction_of_intent || "—"}</td>
                    <td className="mono">{s.confidence != null ? s.confidence.toFixed(2) : "—"}</td>
                    <td><span className="badge skipped">No</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

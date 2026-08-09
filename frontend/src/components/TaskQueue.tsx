import type { ProcessedItem } from "../types";

// The actual routed tasks (created or updated), grouped by owner. Real data.
export default function TaskQueue({
  items,
  names,
}: {
  items: ProcessedItem[];
  names: Record<string, string>;
}) {
  const tasks = items.filter((i) => i.task && (i.decision === "created" || i.decision === "updated"));

  const byOwner: Record<string, number> = {};
  for (const t of tasks) {
    const a = t.assignee_id || t.task?.assignee_id || "u_triage";
    byOwner[a] = (byOwner[a] || 0) + 1;
  }

  return (
    <div>
      <div className="page-head">
        <h2 className="page-title">Task Queue</h2>
        <p className="page-sub">Every email that became a task, and who owns it.</p>
      </div>

      <div className="card">
        <div className="section-head">
          <span className="section-title">{tasks.length} open</span>
          <span className="section-sub">created + updated tasks</span>
        </div>
        {tasks.length === 0 ? (
          <div className="loading">No routed tasks yet. Route a batch from Inbox Ingest &amp; Triage.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Task</th><th>Owner</th><th>Priority</th><th>Company</th><th>Value</th><th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((t) => {
                  const a = t.assignee_id || t.task?.assignee_id || "";
                  return (
                    <tr key={t.email_id}>
                      <td>{t.task?.title || t.subject || t.email_id}</td>
                      <td>{names[a] || a}</td>
                      <td><span className={`badge ${t.task?.priority}`}>{t.task?.priority}</span></td>
                      <td>{t.task?.company_name ?? <span className="null-tag">null</span>}</td>
                      <td className="mono">{t.task?.deal_value_inr == null ? <span className="null-tag">null</span> : `₹${t.task!.deal_value_inr!.toLocaleString("en-IN")}`}</td>
                      <td className="muted">{t.reasoning || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card section">
        <div className="section-head"><span className="section-title">Assignees</span></div>
        {Object.keys(byOwner).length === 0 ? (
          <div className="loading">No assignments yet.</div>
        ) : (
          <div className="chips-row">
            {Object.entries(byOwner).map(([a, n]) => (
              <span key={a} className="chip">{names[a] || a}: {n}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

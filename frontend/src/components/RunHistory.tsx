import { useState } from "react";
import { resetDatabase } from "../api";
import type { Stats } from "../types";
import SelfTest from "./SelfTest";

export default function RunHistory({ stats, onReset }: { stats: Stats | null; onReset: () => void }) {
  const [resetting, setResetting] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);
  const [resetErr, setResetErr] = useState<string | null>(null);

  async function handleReset() {
    const ok = window.confirm("Are you sure you want to reset the database? All tasks and logs will be wiped.");
    if (!ok) return;
    setResetting(true);
    setResetMsg(null);
    setResetErr(null);
    try {
      const res = await resetDatabase();
      const d = res.deleted || {};
      setResetMsg(
        `Database wiped clean successfully — removed ${d.tasks ?? 0} task(s), ${d.email_records ?? 0} log(s), ${d.task_revisions ?? 0} revision(s).`
      );
      onReset();
    } catch (e) {
      setResetErr(`Reset failed: ${(e as Error).message}`);
    } finally {
      setResetting(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <h2 className="page-title">Run History</h2>
        <p className="page-sub">Aggregate stats by run, category, and assignee — plus a live self-test against the twelve worked examples.</p>
      </div>

      <div className="card">
        <div className="section-head"><span className="section-title">Totals</span>
          <span className="section-sub">{stats ? `${stats.run_count} run(s)` : "no data yet"}</span>
        </div>
        {!stats || stats.processed === 0 ? (
          <div className="loading">No runs yet. Route a batch to see history.</div>
        ) : (
          <>
            <div className="stat-strip" style={{ marginTop: 0, borderTop: "none", paddingTop: 0 }}>
              <div><div className="stat-label">processed</div><div className="stat-value">{stats.processed}</div></div>
              <div><div className="stat-label">created</div><div className="stat-value">{stats.created}</div></div>
              <div><div className="stat-label">updated</div><div className="stat-value">{stats.updated}</div></div>
              <div><div className="stat-label">skipped</div><div className="stat-value">{stats.skipped}</div></div>
              <div><div className="stat-label">spurious</div><div className={`stat-value${stats.spurious === 0 ? " green" : ""}`}>{stats.spurious}</div></div>
            </div>

            <div className="two-col">
              <div>
                <div className="k mini-head">By category</div>
                {Object.entries(stats.by_category).map(([c, n]) => (
                  <div key={c} className="kv"><span>{c}</span><span className="mono">{n}</span></div>
                ))}
              </div>
              <div>
                <div className="k mini-head">By assignee</div>
                {Object.entries(stats.by_assignee).map(([a, n]) => (
                  <div key={a} className="kv"><span>{a}</span><span className="mono">{n}</span></div>
                ))}
              </div>
            </div>

            <div className="k mini-head" style={{ marginTop: 16 }}>By run</div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>run_id</th><th>processed</th><th>created</th><th>updated</th><th>skipped</th></tr></thead>
                <tbody>
                  {Object.entries(stats.by_run).map(([run, r]) => (
                    <tr key={run}>
                      <td className="mono">{run.slice(0, 8)}…</td>
                      <td>{r.processed}</td><td>{r.created}</td><td>{r.updated}</td><td>{r.skipped}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="section">
        <SelfTest />
      </div>

      <div className="card section danger-zone">
        <div className="section-head">
          <span className="section-title">Reset dashboard</span>
          <span className="section-sub">wipes all tasks and logs for this candidate</span>
        </div>
        <p className="page-sub" style={{ marginBottom: 12 }}>
          Clears every task, processed-email log, and revision so you can start from a clean slate.
          This cannot be undone.
        </p>
        <button className="btn btn-danger btn-sm" onClick={handleReset} disabled={resetting}>
          {resetting ? "Resetting…" : "Reset database"}
        </button>
        {resetMsg && <div className="reset-ok">✓ {resetMsg}</div>}
        {resetErr && <div className="inline-error">⚠ {resetErr}</div>}
      </div>
    </div>
  );
}

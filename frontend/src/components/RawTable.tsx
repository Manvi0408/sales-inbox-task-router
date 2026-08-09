import type { EmailInput } from "../types";

interface Props {
  emails: EmailInput[];
  onRoute: () => void;
  routing: boolean;
}

function fmtDate(s?: string) {
  if (!s) return "—";
  return s.replace("T", " ").slice(0, 16);
}

export default function RawTable({ emails, onRoute, routing }: Props) {
  return (
    <section className="card section" id="raw">
      <div className="section-head">
        <span className="section-title">2 · raw batch — before routing</span>
        <button className="btn btn-primary btn-sm" onClick={onRoute} disabled={routing}>
          {routing ? "Routing…" : `Route this batch (${emails.length})`}
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>from_name</th>
              <th>from_email</th>
              <th>subject</th>
              <th>received_at</th>
              <th>thread_id</th>
              <th>body preview</th>
            </tr>
          </thead>
          <tbody>
            {emails.map((e) => (
              <tr key={e.email_id}>
                <td>{e.from_name || "—"}</td>
                <td className="mono">{e.from_email || "—"}</td>
                <td>{e.subject || "—"}</td>
                <td className="mono">{fmtDate(e.received_at)}</td>
                <td className="mono">{e.thread_id}</td>
                <td className="muted">{(e.body || "").replace(/\s+/g, " ").slice(0, 80)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

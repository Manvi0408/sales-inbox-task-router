import { useState } from "react";
import { getProcessed, ingest } from "../api";
import type { ProcessedItem } from "../types";
import DecisionTrace from "./DecisionTrace";

// Test ONE real inbound email end-to-end through the existing /ingest pipeline
// (Gemini + rules + Task API). No mocking — it posts a single-email batch and
// reads back the persisted decision trace.
export default function RealEmailReader({
  names,
  onRouted,
}: {
  names: Record<string, string>;
  onRouted: () => void;
}) {
  const [fromName, setFromName] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessedItem | null>(null);

  async function run() {
    if (!subject.trim() && !body.trim()) {
      setErr("Add a subject or body to route.");
      return;
    }
    setBusy(true);
    setErr(null);
    setResult(null);
    const stamp = Date.now();
    const email = {
      email_id: `em_reader_${stamp}`,
      thread_id: `th_reader_${stamp}`,
      message_index: 0,
      from_name: fromName || "Unknown",
      from_email: fromEmail || "unknown@example.com",
      to: "sales@company.com",
      subject,
      body,
      received_at: new Date().toISOString(),
      attachments: [],
      is_reply: false,
    };
    try {
      const res = await ingest([email]);
      const proc = await getProcessed(res.run_id);
      const item = proc.items.find((i) => i.email_id === email.email_id) || null;
      setResult(item);
      onRouted();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <h2 className="page-title">Real Email Reader</h2>
        <p className="page-sub">Route one real inbound email through the live pipeline and see the full decision trace.</p>
      </div>

      <div className="card">
        <div className="form-grid">
          <label className="fld">
            <span>From name</span>
            <input value={fromName} onChange={(e) => setFromName(e.target.value)} placeholder="Suresh Kulkarni" />
          </label>
          <label className="fld">
            <span>From email</span>
            <input value={fromEmail} onChange={(e) => setFromEmail(e.target.value)} placeholder="s.kulkarni@meridiansteel.co.in" />
          </label>
          <label className="fld fld-wide">
            <span>Subject</span>
            <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="RFP - Enterprise Document Management System" />
          </label>
          <label className="fld fld-wide">
            <span>Body</span>
            <textarea
              className="batch-input"
              style={{ minHeight: 140 }}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Paste the email body here…"
            />
          </label>
        </div>
        <div className="input-controls">
          <button className="btn btn-primary btn-sm" onClick={run} disabled={busy}>
            {busy ? "Reading & routing…" : "Read & Route Email"}
          </button>
          {err && <span className="inline-error">⚠ {err}</span>}
        </div>
      </div>

      {result && (
        <div className="card section">
          <div className="section-head"><span className="section-title">Routing result</span>
            <span className="section-sub">{result.email_id}</span>
          </div>
          <DecisionTrace item={result} names={names} />
        </div>
      )}
    </div>
  );
}

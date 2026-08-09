import { useRef, useState } from "react";
import { chat } from "../api";
import type { ChatResponse } from "../types";

interface Msg {
  role: "user" | "bot";
  text: string;
  data?: Record<string, unknown>;
  query?: ChatResponse["query"];
}

const SUGGESTIONS = [
  "How many emails this batch were proposal or RFP related?",
  "How many were marketing versus actual spam we correctly ignored?",
  "Show me everything sitting in triage and why.",
  "What's our spurious rate so far?",
  "Which tasks are high priority but low confidence?",
  "How many emails were about GST refunds?",
  "What's the total deal value of all open RFPs?",
  "Did any thread get updated more than once?",
  "Send Aarti an email about the Meridian Steel RFP.",
];

export default function ChatPanel({ runId }: { runId: string | undefined }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);

  async function ask(q: string) {
    if (!q.trim() || busy) return;
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const res = await chat(q, runId);
      setMsgs((m) => [...m, { role: "bot", text: res.answer, data: res.supporting_data, query: res.query }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "bot", text: `Error: ${(e as Error).message}` }]);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => threadRef.current?.scrollTo(0, threadRef.current.scrollHeight));
    }
  }

  return (
    <section className="card section" id="chat">
      <div className="section-head">
        <span className="section-title">4 · ask about this batch</span>
        <span className="section-sub">grounded — numbers come from stored data, not the model</span>
      </div>

      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <span key={s} className="chip" onClick={() => ask(s)}>{s}</span>
        ))}
      </div>

      <div className="chat-thread" ref={threadRef}>
        {msgs.length === 0 && <div className="loading">Ask a question, or tap a suggestion above.</div>}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.text}</div>
            {m.query && (
              <div className="query-tag">
                intent: {m.query.intent} · filters: {JSON.stringify(m.query.filters)}
              </div>
            )}
            {m.data && Object.keys(m.data).length > 0 && (
              <details className="support">
                <summary>supporting_data</summary>
                <pre>{JSON.stringify(m.data, null, 2)}</pre>
              </details>
            )}
          </div>
        ))}
        {busy && <div className="loading">Thinking…</div>}
      </div>

      <form
        className="chat-form"
        onSubmit={(e) => { e.preventDefault(); ask(input); }}
      >
        <input
          placeholder="Ask about the processed batch…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn-primary btn-sm" type="submit" disabled={busy}>Ask</button>
      </form>
    </section>
  );
}

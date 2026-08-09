// The "How it routes" anchor target — a compact pipeline strip so the nav item
// leads somewhere real, and a first-time visitor understands the flow.

const STEPS = [
  { n: "1", t: "Normalise", d: "Strip HTML and quoted reply chains so values aren't double-counted." },
  { n: "2", t: "Deterministic signals", d: "Parse money & dates; flag PSU tenders, auto-replies, newsletters, spam." },
  { n: "3", t: "Classify", d: "Gemini routes it, given the roster, the rules, and 12 worked examples — hints passed as facts." },
  { n: "4", t: "Override", d: "Rules win last: PSU→Aarti, value routing, 72h→high, spam→no task, invoice≠deal." },
  { n: "5", t: "Write", d: "Create a task or PATCH the thread's task with a revision diff — synchronously." },
];

export default function HowItRoutes() {
  return (
    <section className="card section" id="how">
      <div className="section-head">
        <span className="section-title">How it routes</span>
        <span className="section-sub">deterministic first · LLM second · deterministic overrides last</span>
      </div>
      <div className="how-grid">
        {STEPS.map((s) => (
          <div key={s.n} className="how-step">
            <div className="how-num">{s.n}</div>
            <div className="how-t">{s.t}</div>
            <div className="how-d">{s.d}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

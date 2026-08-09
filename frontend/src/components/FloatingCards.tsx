// The Prefiks-style floating cards: staggered horizontally, slight rotation,
// overlapping vertical offsets, faint connector lines behind, staggered entrance
// + slow out-of-sync float. Each card tells one step of the pipeline story.

interface CardCfg {
  top: number; left: number; width: number; rot: number;
  dur: number; floatDelay: number; enterDelay: number;
  tinted?: boolean;
  labelClass?: string;
  label: string;
  body: string;
}

const CARDS: CardCfg[] = [
  { top: 6, left: 4, width: 214, rot: -2, dur: 6.5, floatDelay: 0, enterDelay: 0.05,
    labelClass: "", label: "em_00142 · inbound", body: "Tender notice BHEL/PROC/2026/0847" },
  { top: 82, left: 44, width: 252, rot: 1.6, dur: 7.4, floatDelay: 0.8, enterDelay: 0.14,
    tinted: true, labelClass: "accent", label: "Rule 3 overrode value routing", body: "PSU tender · ₹6.5L → still Aarti" },
  { top: 160, left: 74, width: 244, rot: -1.4, dur: 5.6, floatDelay: 0.3, enterDelay: 0.23,
    labelClass: "green", label: "Task created · high · conf 0.93", body: "u_aarti · due 2026-08-03" },
  { top: 236, left: 18, width: 240, rot: 2, dur: 8, floatDelay: 1.1, enterDelay: 0.32,
    labelClass: "", label: "Skipped · no task", body: "SEO pitch — marketing words, selling to us" },
];

// Approx card centers for the connector polyline (viewBox 0 0 320 300).
const POINTS = "111,30 170,106 196,184 138,260";

export default function FloatingCards() {
  return (
    <div className="float-stage" aria-hidden="true">
      <svg className="float-svg" viewBox="0 0 320 300" preserveAspectRatio="none">
        <polyline
          points={POINTS}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1"
          strokeOpacity="0.15"
        />
      </svg>
      {CARDS.map((c, i) => (
        <div
          key={i}
          className="fcard-wrap"
          style={{ top: c.top, left: c.left, width: c.width, animationDelay: `${c.enterDelay}s` }}
        >
          <div
            className={`fcard${c.tinted ? " tinted" : ""}`}
            style={{ transform: `rotate(${c.rot}deg)`, animationDuration: `${c.dur}s`, animationDelay: `${c.floatDelay}s` }}
          >
            <div className={`fcard-label ${c.labelClass}`}>{c.label}</div>
            <div className="fcard-body">{c.body}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

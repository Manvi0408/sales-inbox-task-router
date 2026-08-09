import type { Stats } from "../types";
import FloatingCards from "./FloatingCards";

interface Props {
  stats: Stats | null;
  lastRunSeconds: number | null;
  onPaste: () => void;
  onGenerate: () => void;
  onSelfTest: () => void;
}

function fmt(n: number | undefined) {
  return n === undefined ? "—" : n.toLocaleString("en-IN");
}

export default function Hero({ stats, lastRunSeconds, onPaste, onGenerate, onSelfTest }: Props) {
  const hasRun = !!stats && stats.processed > 0;
  return (
    <header className="hero-band" id="top">
      {hasRun && (
        <div className="pill">
          <span className="dot" />
          <span>
            Live · {fmt(stats!.processed)} emails routed
            {lastRunSeconds != null ? ` in ${lastRunSeconds}s` : ""}
          </span>
        </div>
      )}

      <div className="hero-grid">
        <div>
          <h1 className="headline">
            The inbox that<br />
            <span className="accent">routes itself.</span>
          </h1>
          <p className="hero-copy">
            150–250 emails a day, sorted to the right owner before anyone opens them.
            Every decision shows its reasoning — which rule fired, what the model proposed,
            and why the spam stayed out.
          </p>
          <div className="hero-actions">
            <button className="btn btn-primary" onClick={onPaste}>Paste a batch</button>
            <button className="btn btn-outline" onClick={onGenerate}>Generate 250 samples</button>
            <button className="btn btn-outline" onClick={onSelfTest}>Run self-test</button>
          </div>
        </div>

        <FloatingCards />
      </div>

      <div className="stat-strip">
        <div><div className="stat-label">processed</div><div className="stat-value">{fmt(stats?.processed ?? 0)}</div></div>
        <div><div className="stat-label">created</div><div className="stat-value">{fmt(stats?.created ?? 0)}</div></div>
        <div><div className="stat-label">updated</div><div className="stat-value">{fmt(stats?.updated ?? 0)}</div></div>
        <div><div className="stat-label">skipped</div><div className="stat-value">{fmt(stats?.skipped ?? 0)}</div></div>
        <div>
          <div className="stat-label">spurious</div>
          <div className={`stat-value${(stats?.spurious ?? 0) === 0 ? " green" : ""}`}>{fmt(stats?.spurious ?? 0)}</div>
        </div>
      </div>
    </header>
  );
}

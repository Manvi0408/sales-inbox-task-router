import { Icon } from "./Icon";

export type PageId =
  | "inbox" | "ingest" | "queue" | "reader" | "results" | "skipped"
  | "decisions" | "review" | "history";

const GROUPS: { label: string; items: { id: PageId; label: string; icon: string }[] }[] = [
  {
    label: "Inbox",
    items: [
      { id: "inbox", label: "Inbox", icon: "inbox" },
      { id: "ingest", label: "Inbox Ingest & Triage", icon: "triage" },
      { id: "queue", label: "Task Queue", icon: "queue" },
      { id: "reader", label: "Real Email Reader", icon: "reader" },
      { id: "results", label: "Results", icon: "results" },
      { id: "skipped", label: "Skipped Noise Log", icon: "skipped" },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { id: "decisions", label: "Decision Center", icon: "decisions" },
      { id: "review", label: "Review Queue", icon: "review" },
      { id: "history", label: "Run History", icon: "history" },
    ],
  },
];

export default function Sidebar({
  active,
  onNavigate,
}: {
  active: PageId;
  onNavigate: (id: PageId) => void;
}) {
  return (
    <aside className="sidebar">
      <div className="sb-brand">
        <div className="brand-mark">✦</div>
        <span className="brand-name">Inbox Router</span>
      </div>
      {GROUPS.map((g) => (
        <div key={g.label} className="sb-section">
          <div className="sb-group">{g.label}</div>
          {g.items.map((it) => (
            <button
              key={it.id}
              className={`sb-item${active === it.id ? " active" : ""}`}
              onClick={() => onNavigate(it.id)}
              aria-current={active === it.id ? "page" : undefined}
            >
              <span className="ic"><Icon name={it.icon} /></span>
              <span>{it.label}</span>
            </button>
          ))}
        </div>
      ))}
    </aside>
  );
}

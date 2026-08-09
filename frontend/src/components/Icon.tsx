// Minimal 16px stroke icons for the sidebar. currentColor so active state tints them.
const PATHS: Record<string, string> = {
  inbox: '<path d="M4 13h4l2 3h4l2-3h4"/><path d="M4 13l2-8h12l2 8v6H4z"/>',
  triage: '<path d="M12 3v10"/><path d="M8 9l4 4 4-4"/><path d="M4 18h16"/>',
  queue: '<path d="M4 6h16M4 12h16M4 18h11"/>',
  reader: '<path d="M4 20h4L20 8l-4-4L4 16z"/><path d="M14 6l4 4"/>',
  results: '<rect x="4" y="5" width="16" height="14" rx="1"/><path d="M4 10h16M9 10v9"/>',
  skipped: '<circle cx="12" cy="12" r="8"/><path d="M6.5 6.5l11 11"/>',
  decisions: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',
  review: '<path d="M6 21V4"/><path d="M6 4h11l-2 4 2 4H6"/>',
  history: '<path d="M4 12a8 8 0 1 0 3-6.2"/><path d="M4 4v4h4"/>',
};

export function Icon({ name }: { name: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      dangerouslySetInnerHTML={{ __html: PATHS[name] || "" }}
    />
  );
}

/** Compact relative timestamp; title carries the full absolute local string. */

export function relativeTime(iso: string): { text: string; title: string } {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return { text: "", title: "" };
  const title = date.toLocaleString();
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60_000) return { text: "just now", title };
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return { text: `${minutes}m ago`, title };
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return { text: `${hours}h ago`, title };
  const days = Math.floor(hours / 24);
  if (days < 7) return { text: `${days}d ago`, title };
  return { text: date.toLocaleDateString(), title };
}

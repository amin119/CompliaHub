const SEVERITY_STYLES: Record<string, string> = {
  CRITICAL: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400",
  HIGH: "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-400",
  MEDIUM: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400",
  LOW: "bg-surface text-muted",
  INFORMATIONAL: "bg-surface text-muted",
};

/**
 * Severity is a different axis from `StatusBadge`'s scan/document
 * lifecycle status (pending/ready/failed) — a sibling component rather
 * than an overload of `StatusBadge`'s color logic.
 */
export default function SeverityBadge({ severity }: { severity: string }) {
  const style = SEVERITY_STYLES[severity] ?? "bg-surface text-muted";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}>{severity}</span>
  );
}

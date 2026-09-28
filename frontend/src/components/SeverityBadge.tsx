import { BADGE_BASE } from "@/lib/ui";

/**
 * Severity deliberately stays on the conventional red → orange → amber →
 * neutral ramp rather than being tinted with the brand palette. Risk colour
 * is a functional scale an analyst reads at a glance, it has to survive
 * print, and borrowing the brand's own accent for it would make "this is
 * dangerous" and "this is clickable" the same colour.
 */
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
  return <span className={`${BADGE_BASE} ${style}`}>{severity}</span>;
}

/**
 * A labeled horizontal bar for a raw count — turns the report's three
 * breakdown tables (severity / status / framework) from a flat list of
 * numbers into something that reads at a glance, the way the landing page's
 * own scanner-pipeline mockup showed a report before this page actually had
 * one.
 *
 * The bar's width is proportional to `count / max` **within its own
 * category** (e.g. severity counts compared only against the largest
 * severity count) — never against a total, and never rendered as a
 * percentage. That distinction matters: this project has a standing rule
 * that nothing in a report may read as an aggregate compliance score, and a
 * bar sized against "how many, relative to the biggest bucket here" stays a
 * count, not a computed rate.
 */
export default function BarRow({
  label,
  count,
  max,
  barClassName = "bg-accent",
  labelSlot,
  labelWidthClassName = "w-28",
}: {
  label: string;
  count: number;
  max: number;
  barClassName?: string;
  /** Overrides the plain text label — e.g. a `SeverityBadge`. */
  labelSlot?: React.ReactNode;
  /** Widen when `labelSlot` renders a longer badge (e.g. finding status). */
  labelWidthClassName?: string;
}) {
  const widthPercent = max <= 0 ? 0 : Math.max(count > 0 ? 4 : 0, (count / max) * 100);

  return (
    <div className="flex items-center gap-3 py-1">
      <span className={`shrink-0 text-xs text-muted ${labelWidthClassName}`}>
        {labelSlot ?? label}
      </span>
      <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface">
        <span
          className={`block h-full rounded-full transition-[width] duration-[var(--dur-slow)] ease-[var(--ease-out-quart)] ${barClassName}`}
          style={{ width: `${widthPercent}%` }}
        />
      </span>
      <span className="w-6 shrink-0 text-right text-sm font-medium text-foreground">{count}</span>
    </div>
  );
}

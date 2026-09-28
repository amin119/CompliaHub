export type Stat = {
  label: string;
  /** Omit when `content` fully replaces the plain numeric display. */
  value?: string | number | null;
  /** e.g. a language/framework chip list, or a differently-colored value */
  content?: React.ReactNode;
};

/**
 * A row of labeled stats in its own card — replaces the plain
 * `flex flex-wrap gap-x-6` text strips that used to sit at the top of the
 * scan detail and report pages. The same data, but given a real visual
 * anchor (a bordered card, a consistent label/value rhythm) instead of
 * reading as an afterthought line of text above the real content.
 */
export default function StatGrid({ stats }: { stats: Stat[] }) {
  return (
    <div className="mb-6 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-surface-border bg-surface-border sm:grid-cols-4">
      {stats.map((stat) => (
        <div key={stat.label} className="bg-surface-raised px-4 py-3.5">
          <p className="text-xs text-muted">{stat.label}</p>
          {stat.content ? (
            <div className="mt-1.5 flex flex-wrap gap-1.5">{stat.content}</div>
          ) : (
            <p className="mt-1 text-lg font-semibold text-foreground">{stat.value}</p>
          )}
        </div>
      ))}
    </div>
  );
}

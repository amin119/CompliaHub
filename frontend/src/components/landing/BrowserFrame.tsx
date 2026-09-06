/**
 * A restrained browser-chrome frame around the product-preview mockups —
 * three dots and a thin address bar carrying the real route — so a preview
 * reads as "a look at the actual running application" rather than a
 * floating, context-less card.
 *
 * Every preview it wraps is cosmetic: none of them call the real API (see
 * `DemoCitation` / `AnimatedConversation`).
 */
export default function BrowserFrame({
  path,
  children,
  className,
}: {
  path: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`overflow-hidden rounded-3xl border border-surface-border bg-surface-raised shadow-[0_24px_60px_-32px_rgba(20,16,25,0.45)] ${className ?? ""}`}
    >
      <div className="flex items-center gap-2 border-b border-surface-border bg-surface px-4 py-3">
        <span className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-surface-border" />
          <span className="h-2.5 w-2.5 rounded-full bg-surface-border" />
          <span className="h-2.5 w-2.5 rounded-full bg-surface-border" />
        </span>
        <span className="ml-2 truncate rounded-full bg-surface-raised px-3 py-1 text-[11px] text-muted">
          {path}
        </span>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

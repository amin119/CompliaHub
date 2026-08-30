/**
 * A restrained browser-chrome frame around the product-preview mockups —
 * three dots, a thin address bar with the real route. Used so a preview
 * reads as "a look at the actual running application" rather than a
 * floating, context-less card. Rounded generously (rounded-3xl) to match
 * this design's soft, rounded visual language.
 */
export default function BrowserFrame({
  path,
  children,
}: {
  path: string;
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-3xl border border-surface-border bg-surface shadow-sm">
      <div className="flex items-center gap-2 border-b border-surface-border px-4 py-3">
        <span className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-surface-border" />
          <span className="h-2.5 w-2.5 rounded-full bg-surface-border" />
          <span className="h-2.5 w-2.5 rounded-full bg-surface-border" />
        </span>
        <span className="ml-2 rounded-full bg-surface px-3 py-1 text-[11px] text-muted">
          {path}
        </span>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

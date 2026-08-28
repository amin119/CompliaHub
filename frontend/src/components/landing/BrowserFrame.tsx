/**
 * A restrained browser-chrome frame around the product-preview mockups —
 * three dots, a thin address bar with the real route, nothing skeuomorphic
 * beyond that. Used so Section 11's previews read as "a look at the actual
 * running application" rather than a floating, context-less card.
 */
export default function BrowserFrame({
  path,
  children,
}: {
  path: string;
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-sm border border-landing-border bg-landing-surface">
      <div className="flex items-center gap-2 border-b border-landing-border px-4 py-2.5">
        <span className="flex gap-1.5">
          <span className="h-2 w-2 rounded-full bg-landing-border" />
          <span className="h-2 w-2 rounded-full bg-landing-border" />
          <span className="h-2 w-2 rounded-full bg-landing-border" />
        </span>
        <span className="ml-2 rounded-full bg-landing-bg px-3 py-0.5 text-[11px] text-landing-fg/50">
          {path}
        </span>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

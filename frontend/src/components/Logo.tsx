/**
 * Inline SVG mark — a hexagon (the "standard"/framework) enclosing three
 * connected nodes (the graph) — reused in both the marketing nav and the
 * app shell nav so brand identity stays consistent across the landing page
 * and the product itself. `currentColor` throughout so it inherits
 * whatever text color its wrapper sets, no separate light/dark asset.
 */
export default function Logo({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <path
        d="M16 2.5 28.5 9.5V22.5L16 29.5 3.5 22.5V9.5L16 2.5Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <circle cx="16" cy="11" r="2.1" fill="currentColor" />
      <circle cx="11" cy="19.5" r="2.1" fill="currentColor" />
      <circle cx="21" cy="19.5" r="2.1" fill="currentColor" />
      <path
        d="M16 13.1 12.4 17.7M16 13.1l3.6 4.6M13.1 19.5h5.8"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

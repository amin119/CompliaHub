/**
 * A shimmering placeholder block — used wherever a list is still loading
 * its first page (documents/scans on mount) so the page shows structure
 * immediately instead of a blank beat before "No X yet" or real content
 * pops in. The shimmer itself is `globals.css`'s `.animate-shimmer`
 * (a background-position sweep, not JS-driven) so it costs nothing to
 * keep running.
 */
export default function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-shimmer rounded-2xl bg-surface ${className}`} />;
}

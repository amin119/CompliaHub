/**
 * The repeating diagonal band. A plain CSS keyframe loop
 * (`.marquee-track`, globals.css), not GSAP: it never needs to react to
 * scroll position, and it already respects `prefers-reduced-motion` via a
 * media query rather than a JS check.
 *
 * `bg-marquee` (not `bg-cta`): the band carries the highlighter, so it
 * reads as a *marked* strip through the page rather than a dimmed copy of
 * the primary button. Text is `--mark-contrast` dark ink in both themes —
 * paper-white on amber would fail contrast badly, and dark-on-yellow is how
 * a real highlighter works anyway.
 *
 * The separator is a small solid diamond rather than the sparkle glyph this
 * previously used: ✨ has become shorthand for "AI did this", which is
 * exactly the wrong signal on a band listing what the product verifiably
 * supports.
 *
 * Content is duplicated exactly once so translating by -50% lands on an
 * identical frame — the standard seamless-marquee trick.
 */
export default function Marquee({
  items,
  reverse = false,
}: {
  items: string[];
  reverse?: boolean;
}) {
  const repeated = [...items, ...items];

  return (
    <div
      className={`bg-marquee overflow-hidden py-3 sm:py-4 ${reverse ? "rotate-1" : "-rotate-1"}`}
      aria-hidden="true"
    >
      <div
        className={`${
          reverse ? "marquee-track-reverse" : "marquee-track"
        } flex w-max items-center gap-4 whitespace-nowrap`}
      >
        {repeated.map((item, index) => (
          <span
            key={index}
            className="font-display text-mark-contrast flex items-center gap-4 text-sm font-semibold tracking-tight sm:text-base"
          >
            {item}
            <span className="h-1.5 w-1.5 rotate-45 bg-current opacity-60" />
          </span>
        ))}
      </div>
    </div>
  );
}

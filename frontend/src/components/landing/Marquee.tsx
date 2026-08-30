/**
 * The reference design's signature repeating diagonal banner — a skewed,
 * full-width gradient band with bold uppercase text scrolling
 * horizontally, a sparkle glyph between repeats (matching the dark-mode
 * "Loker" reference image, which uses a sparkle/star separator rather
 * than a plain "+"). Plain CSS keyframe loop (`.marquee-track`,
 * globals.css), not GSAP: it never needs to react to scroll position,
 * just loop at a constant speed, and it already respects
 * `prefers-reduced-motion` via a media query rather than a JS check.
 *
 * `bg-marquee` (not `bg-cta`) so the band can carry its own palette —
 * the same blue/purple/pink gradient as the CTA buttons in light mode,
 * but a distinct warm orange in dark mode (see globals.css's
 * `--marquee-fill` token) so the banner doesn't just look like a dimmed
 * copy of the accent color.
 *
 * The track content is duplicated exactly once (`[...items, ...items]`)
 * so translating it by -50% lands back on an identical frame — the
 * standard seamless-marquee trick.
 */
function SparkleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5 shrink-0">
      <path d="M12 2c.6 3.4 1.3 5.7 2.4 6.9C15.6 10.1 17.8 10.8 21 11.4c-3.2.6-5.4 1.3-6.6 2.5-1.1 1.2-1.8 3.5-2.4 6.9-.6-3.4-1.3-5.7-2.4-6.9C8.4 12.7 6.2 12 3 11.4c3.2-.6 5.4-1.3 6.6-2.5C10.7 7.7 11.4 5.4 12 2Z" />
    </svg>
  );
}

export default function Marquee({ text }: { text: string }) {
  const items = Array.from({ length: 8 }, () => text);

  return (
    <div className="bg-marquee -rotate-1 overflow-hidden py-3 sm:py-4" aria-hidden="true">
      <div className="marquee-track flex w-max gap-3 whitespace-nowrap">
        {[...items, ...items].map((item, i) => (
          <span
            key={i}
            className="font-display flex items-center gap-3 text-sm font-bold tracking-wide text-white uppercase sm:text-base"
          >
            {item}
            <SparkleIcon />
          </span>
        ))}
      </div>
    </div>
  );
}

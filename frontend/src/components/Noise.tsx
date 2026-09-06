/**
 * A fixed, non-interactive paper-grain layer. What keeps the warm ground
 * reading as a *surface* rather than a flat fill — the tactile half of the
 * ink-and-paper idea.
 *
 * Opacity is driven by `--noise-opacity`, which each theme tunes (grain
 * reads heavier on a dark ground), and the whole layer is removed under
 * `prefers-reduced-motion` and in print — see `.grain-overlay` in
 * globals.css. A server component: it renders one static div and has no
 * behaviour of its own.
 */
export default function Noise() {
  return <div aria-hidden="true" className="grain-overlay" />;
}

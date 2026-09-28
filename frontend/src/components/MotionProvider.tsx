"use client";

import { MotionConfig } from "motion/react";

/**
 * Makes `motion/react` honour `prefers-reduced-motion` product-wide.
 *
 * The GSAP side of the codebase checks the preference explicitly
 * (`prefersReducedMotion()` in lib/gsap.ts) and the CSS side has its own
 * `@media (prefers-reduced-motion: reduce)` block — but Motion's components
 * ignore the preference entirely unless a `MotionConfig` says otherwise, so
 * every `motion.div` in the app (the upload sweep, the pipeline pulse, the
 * chat thread indicator, the tab underline) was animating regardless. This
 * closes that gap in one place.
 *
 * `"user"` is Motion's own setting for "follow the OS preference": transform
 * and layout animations are disabled while opacity and colour still animate,
 * so state changes stay legible instead of snapping invisibly.
 */
export default function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

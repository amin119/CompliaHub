"use client";

import { useEffect } from "react";
import { ReactLenis, useLenis } from "lenis/react";
import { gsap, ScrollTrigger } from "@/lib/gsap";

/**
 * Wraps the landing page in Lenis smooth scroll, synced to GSAP's own
 * ticker so ScrollTrigger-pinned/scrubbed animations (Phases 2-4) stay in
 * lockstep with Lenis's eased scroll position rather than reading a native
 * scroll value that's a frame behind it — the standard GSAP+Lenis
 * integration recipe.
 *
 * `root` (not `asChild`): Lenis patches `window` scroll directly rather
 * than creating an isolated scroll container, which is what a normal
 * full-page marketing site wants. Scoped to this component's mount
 * lifetime only — navigating to `/chat` or `/documents` unmounts this
 * (a different route's component tree), and `ReactLenis` tears its
 * instance down on unmount, so the app's own pages are never affected.
 *
 * Respects `prefers-reduced-motion`: Lenis isn't constructed at all when
 * the user has that preference — native scroll behavior applies instead.
 * Read via a lazy `useState` initializer, not an effect: `ReactLenis` with
 * `root` renders its children directly with no extra DOM (verified against
 * its source), so switching between "no wrapper" and "Lenis-wrapped" is
 * otherwise invisible to hydration — but computing this in an effect would
 * still flip the wrapper *type* one render after mount for most users (no
 * preference set → `false`), which remounts every section beneath it once.
 * A lazy initializer runs during the client's first render (window exists
 * by then, even though it doesn't during SSR), so the correct value is
 * already in place before anything downstream ever mounts.
 */
export default function SmoothScroll({ children }: { children: React.ReactNode }) {
  const reducedMotion =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reducedMotion) {
    return <>{children}</>;
  }

  return (
    <ReactLenis root options={{ autoRaf: false }}>
      <LenisGsapSync />
      {children}
    </ReactLenis>
  );
}

function LenisGsapSync() {
  const lenis = useLenis();

  useEffect(() => {
    if (!lenis) return;

    lenis.on("scroll", ScrollTrigger.update);

    const tick = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(tick);
      lenis.off("scroll", ScrollTrigger.update);
    };
  }, [lenis]);

  return null;
}

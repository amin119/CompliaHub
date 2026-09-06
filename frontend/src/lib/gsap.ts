/**
 * Registers every GSAP plugin the landing page needs, exactly once,
 * client-side only. GreenSock's formerly-Club plugins (ScrollTrigger,
 * SplitText, DrawSVG, MorphSVG, MotionPath) now ship inside the public
 * `gsap` package itself — no private registry auth needed — but
 * ScrollTrigger specifically touches `window`/`document` at registration
 * time, so this must never run during SSR. Every component that needs GSAP
 * imports from here (not directly from `"gsap"`), so registration always
 * happens before any tween or ScrollTrigger is created.
 *
 * SplitText drives the line-by-line masked headline reveals (see
 * `RevealText`) — the signature motion of this design.
 */
import { gsap } from "gsap";
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin";
import { MorphSVGPlugin } from "gsap/MorphSVGPlugin";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger, SplitText, DrawSVGPlugin, MorphSVGPlugin, MotionPathPlugin);
}

/** The shared motion vocabulary, mirroring the `--ease-*` / `--dur-*`
 * tokens in globals.css so JS-driven and CSS-driven motion agree. */
export const MOTION = {
  easeOut: "expo.out",
  easeOutSoft: "power3.out",
  easeMicro: "power2.out",
  durFast: 0.22,
  durBase: 0.42,
  durSlow: 0.8,
  durHero: 1.0,
  stagger: 0.08,
} as const;

/** Single source of truth for the reduced-motion check. Every animated
 * component calls this before creating tweens and shows the final state
 * instead when it returns true. */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export { gsap, ScrollTrigger, SplitText, DrawSVGPlugin, MorphSVGPlugin, MotionPathPlugin };

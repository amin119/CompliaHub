/**
 * Registers every GSAP plugin the landing rebuild needs, exactly once,
 * client-side only. GreenSock's formerly-Club plugins (ScrollTrigger,
 * DrawSVGPlugin, MorphSVGPlugin, MotionPathPlugin) now ship inside the
 * public `gsap` package itself — no private registry auth needed — but
 * ScrollTrigger specifically touches `window`/`document` at registration
 * time, so this must never run during SSR. Every landing component that
 * needs GSAP imports `gsap` from here (not directly from `"gsap"`), so
 * registration always happens before any tween/ScrollTrigger is created.
 */
import { gsap } from "gsap";
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin";
import { MorphSVGPlugin } from "gsap/MorphSVGPlugin";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";
import { ScrollTrigger } from "gsap/ScrollTrigger";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger, DrawSVGPlugin, MorphSVGPlugin, MotionPathPlugin);
}

export { gsap, ScrollTrigger, DrawSVGPlugin, MorphSVGPlugin, MotionPathPlugin };

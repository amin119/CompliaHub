"use client";

import { useEffect, useRef } from "react";
import { gsap, prefersReducedMotion } from "@/lib/gsap";

/**
 * Pulls an element a fraction of the way toward the pointer while the
 * pointer is near it, and springs it back on leave. Used on the landing
 * page's primary CTAs and logo.
 *
 * No-ops entirely on coarse pointers (there is nothing to be magnetic
 * toward on a touchscreen) and under `prefers-reduced-motion`, and always
 * resets the transform on unmount so a magnetised element can never be left
 * stranded off-centre.
 */
export function useMagnetic<T extends HTMLElement>(strength = 0.3, radius = 80) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (!window.matchMedia("(pointer: fine)").matches || prefersReducedMotion()) return;

    // quickTo avoids allocating a fresh tween on every pointermove.
    const moveX = gsap.quickTo(element, "x", { duration: 0.4, ease: "power3.out" });
    const moveY = gsap.quickTo(element, "y", { duration: 0.4, ease: "power3.out" });

    function handleMove(event: PointerEvent) {
      const rect = element!.getBoundingClientRect();
      const centreX = rect.left + rect.width / 2;
      const centreY = rect.top + rect.height / 2;
      const deltaX = event.clientX - centreX;
      const deltaY = event.clientY - centreY;
      const reach = radius + Math.max(rect.width, rect.height) / 2;

      if (Math.hypot(deltaX, deltaY) > reach) {
        moveX(0);
        moveY(0);
        return;
      }
      moveX(deltaX * strength);
      moveY(deltaY * strength);
    }

    function reset() {
      moveX(0);
      moveY(0);
    }

    window.addEventListener("pointermove", handleMove, { passive: true });
    element.addEventListener("pointerleave", reset);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      element.removeEventListener("pointerleave", reset);
      gsap.set(element, { x: 0, y: 0 });
    };
  }, [strength, radius]);

  return ref;
}

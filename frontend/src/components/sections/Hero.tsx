"use client";

import { useRef } from "react";
import Link from "next/link";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";
import Logo from "@/components/Logo";

/**
 * Rebuilt to match the reference design (home page design/home page.svg):
 * a bold two-line contrast headline ("we don't do X, we do Y") with a
 * small inline accent icon, a soft gradient-wash background, and a single
 * CTA. The reference's hero also has an email-capture input next to its
 * "Get Started" button — dropped here, since this platform has no
 * waitlist/signup backend for it to submit to; a second, real link
 * ("See how it works") takes its place instead of a non-functional input.
 *
 * The two lines are each their own non-wrapping flex row sized with a
 * `clamp()` so the headline is exactly 2 lines at every supported viewport
 * width, rather than 2 lines only by accident on a couple of breakpoints
 * (the reference itself renders as exactly 2 lines, each carrying one
 * inline image/icon badge — reproduced here as a "not keyword search"
 * badge on line 1 and the brand mark on line 2, since no photography
 * exists for this platform).
 */
export default function Hero() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const items = gsap.utils.toArray<HTMLElement>(".hero-reveal");
      if (reducedMotion) {
        gsap.set(items, { opacity: 1, y: 0 });
        return;
      }
      gsap.from(items, { opacity: 0, y: 18, duration: 0.7, stagger: 0.12, ease: "power2.out" });
    },
    { scope: containerRef },
  );

  return (
    <section
      ref={containerRef}
      className="relative overflow-hidden px-4 pt-20 pb-24 text-center sm:px-8"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 0%, var(--pink) 0%, transparent 70%), radial-gradient(40% 40% at 85% 10%, var(--surface-blue) 0%, transparent 70%)",
        }}
      />

      <h1 className="hero-reveal font-display mx-auto max-w-4xl font-bold text-foreground">
        <span className="flex flex-nowrap items-center justify-center gap-x-2 text-[clamp(1.5rem,6.5vw,3.75rem)] leading-[1.15] whitespace-nowrap">
          We don&apos;t do
          <span className="inline-flex h-[0.9em] w-[0.9em] shrink-0 items-center justify-center rounded-full bg-surface align-middle">
            <svg viewBox="0 0 24 24" fill="none" className="h-[0.5em] w-[0.5em] text-muted">
              <circle cx="10" cy="10" r="6" stroke="currentColor" strokeWidth="1.8" />
              <path d="m20 20-4.35-4.35" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <path d="M5 5 19 19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </span>
          keyword search,
        </span>
        <span className="mt-1 flex flex-nowrap items-center justify-center gap-x-2 text-[clamp(1.5rem,6.5vw,3.75rem)] leading-[1.15] whitespace-nowrap">
          we do
          <span className="bg-cta inline-flex h-[0.9em] w-[0.9em] shrink-0 items-center justify-center rounded-full align-middle">
            <Logo className="h-[0.5em] w-[0.5em] text-white" />
          </span>
          compliance reasoning.
        </span>
      </h1>

      <p className="hero-reveal mx-auto mt-6 max-w-xl text-base text-muted sm:text-lg">
        Now you can get compliance answers grounded in evidence. Just ask a question or upload
        your standards.
      </p>

      <div className="hero-reveal mt-8 flex flex-wrap items-center justify-center gap-4">
        <Link
          href="/chat"
          className="rounded-full bg-cta px-7 py-3.5 text-sm font-semibold text-accent-foreground shadow-sm transition-transform hover:scale-105"
        >
          Get Started
        </Link>
        <a
          href="#showcase"
          className="rounded-full border border-surface-border px-7 py-3.5 text-sm font-semibold text-foreground transition-colors hover:border-accent hover:text-accent"
        >
          See how it works
        </a>
      </div>
    </section>
  );
}

"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";
import { squareSpiral, resolvedPath, type Point } from "@/lib/labyrinth";
import Eyebrow from "./Eyebrow";

const CENTER: Point = [430, 250];
const SPIRAL = squareSpiral(CENTER, 170, 12, 15);
const RESOLVED_D = resolvedPath(SPIRAL.points[SPIRAL.points.length - 1], [560, SPIRAL.points[SPIRAL.points.length - 1][1]], 6);

const FRAGMENTS = [
  { label: "GDPR", pointIndex: 1 },
  { label: "Article 17", pointIndex: 3 },
  { label: "Policy 4.2", pointIndex: 5 },
  { label: "Control", pointIndex: 7 },
  { label: "Requirement", pointIndex: 9 },
  { label: "Evidence", pointIndex: 11 },
  { label: "Risk", pointIndex: 12 },
];

/**
 * The hero's seven-beat story (brief section 5), sequenced on a single
 * GSAP timeline: fragments appear → the labyrinth draws (DrawSVG) →
 * a thread travels through it (MotionPath), highlighting fragments as it
 * nears them → the labyrinth resolves into a clean path (MorphSVG) → the
 * headline settles in last.
 *
 * One deliberate simplification from the brief's exact 7 steps: stages 2
 * ("thin connecting lines appear") and 3 ("lines resolve into the
 * labyrinth") are combined into a single DrawSVG reveal of the labyrinth
 * path itself, rather than drawing a separate set of loose connector
 * lines and MorphSVG-ing *those* into the labyrinth — doing that would
 * need a second hand-authored path with a compatible point count purely
 * for a few hundred milliseconds of visual difference. MorphSVG is used
 * for the one transformation that actually needs it: the labyrinth
 * resolving into the clean path at the end.
 */
export default function Hero() {
  const containerRef = useRef<HTMLDivElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const [reducedMotionDone, setReducedMotionDone] = useState(false);

  useGSAP(
    () => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      if (reducedMotion) {
        // Skip straight to the resolved end-state: labyrinth dimmed, clean
        // path visible, headline already in place — a simple opacity fade,
        // no timeline at all, checked before any GSAP object is created.
        setReducedMotionDone(true);
        return;
      }

      const fragments = gsap.utils.toArray<SVGGElement>(".hero-fragment");
      const marker = document.querySelector<SVGCircleElement>(".hero-marker");
      const path = pathRef.current;
      if (!path || !marker) return;

      const tl = gsap.timeline({ defaults: { ease: "power2.out" } });

      tl.from(fragments, { opacity: 0, scale: 0.7, transformOrigin: "center", duration: 0.45, stagger: 0.1 });

      tl.fromTo(
        path,
        { drawSVG: "0%" },
        { drawSVG: "100%", duration: 2, ease: "power1.inOut" },
        "+=0.1",
      );

      const travelStart = tl.duration();
      const travelDuration = 1.8;
      tl.set(marker, { opacity: 1 });
      tl.to(
        marker,
        {
          motionPath: { path, align: path, alignOrigin: [0.5, 0.5] },
          duration: travelDuration,
          ease: "power1.inOut",
        },
        travelStart,
      );

      // Each fragment highlights roughly when the marker reaches its
      // corner of the spiral — an approximation (MotionPath distributes
      // progress by arc length, not point index), close enough for the
      // effect to read as "the thread notices this as it passes."
      fragments.forEach((fragment, i) => {
        const t = i / (fragments.length - 1);
        tl.to(
          fragment,
          { opacity: 1, scale: 1.08, duration: 0.3, yoyo: true, repeat: 1 },
          travelStart + t * travelDuration,
        );
      });

      // DrawSVG leaves an explicit stroke-dasharray/dashoffset sized to the
      // spiral's path length; clearing it before MorphSVG changes the `d`
      // attribute avoids the stroke rendering clipped against geometry
      // that no longer matches those pixel-based values.
      tl.set(path, { clearProps: "strokeDasharray,strokeDashoffset" }, "+=0.15");
      tl.to(path, { morphSVG: RESOLVED_D, duration: 1.1, ease: "power2.inOut" });
      tl.to(".hero-fragment", { opacity: 0.28, duration: 0.7 }, "<");
      tl.to(marker, { opacity: 0, duration: 0.3 }, "<");

      tl.from(".hero-copy", { opacity: 0, y: 14, duration: 0.6, stagger: 0.1 }, "+=0.1");
    },
    { scope: containerRef },
  );

  return (
    <section
      ref={containerRef}
      className="font-landing-sans relative mx-auto flex w-full max-w-6xl flex-1 flex-col items-center gap-14 px-4 pt-20 pb-28 sm:px-8 lg:flex-row lg:items-center lg:gap-6 lg:pt-24"
    >
      <div className="max-w-xl lg:w-2/5">
        <div className="hero-copy">
          <Eyebrow>Agentic RAG for compliance intelligence</Eyebrow>
        </div>
        <h1 className="hero-copy font-landing-serif mt-5 text-5xl leading-[1.05] font-normal text-balance text-landing-fg sm:text-6xl">
          Navigate complexity.
        </h1>
        <p className="hero-copy mt-6 text-base leading-relaxed text-landing-fg/70">
          An agentic intelligence layer that retrieves, connects, and reasons across your
          compliance knowledge — so every answer has a path back to evidence.
        </p>
        <div className="hero-copy mt-9 flex flex-wrap items-center gap-x-8 gap-y-4">
          <Link
            href="/chat"
            className="rounded-sm bg-landing-accent px-6 py-3 text-sm font-medium text-landing-accent-fg transition-opacity hover:opacity-90"
          >
            Enter the platform
          </Link>
          <a
            href="#labyrinth"
            className="border-b border-landing-fg/30 pb-0.5 text-sm font-medium text-landing-fg transition-colors hover:border-landing-accent hover:text-landing-accent"
          >
            Explore the intelligence
          </a>
        </div>
      </div>

      <div className="w-full lg:w-3/5">
        <svg
          viewBox="0 0 620 460"
          className="h-auto w-full max-w-xl text-landing-border"
          role="img"
          aria-label="A labyrinth of scattered regulatory fragments, through which a thread travels and resolves into a clear path"
        >
          {FRAGMENTS.map((fragment) => {
            const [x, y] = SPIRAL.points[fragment.pointIndex];
            return (
              <g
                key={fragment.label}
                className="hero-fragment"
                style={reducedMotionDone ? { opacity: 0.28 } : undefined}
              >
                <rect
                  x={x - 2}
                  y={y - 12}
                  width={fragment.label.length * 6.2 + 14}
                  height={18}
                  rx={2}
                  className="fill-landing-surface stroke-landing-border"
                  strokeWidth={1}
                />
                <text
                  x={x + fragment.label.length * 3.1 + 5}
                  y={y + 1}
                  textAnchor="middle"
                  className="fill-landing-fg/60"
                  style={{ fontSize: 9.5, letterSpacing: "0.02em" }}
                >
                  {fragment.label}
                </text>
              </g>
            );
          })}

          <path
            ref={pathRef}
            d={reducedMotionDone ? RESOLVED_D : SPIRAL.d}
            fill="none"
            className="stroke-landing-accent"
            strokeWidth={1.3}
            strokeLinejoin="round"
            style={reducedMotionDone ? { opacity: 0.9 } : undefined}
          />
          <circle className="hero-marker fill-landing-accent" r={4.5} opacity={0} />
        </svg>
      </div>
    </section>
  );
}

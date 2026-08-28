"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";
import { squareSpiral, type Point } from "@/lib/labyrinth";
import Eyebrow from "./Eyebrow";

const CENTER: Point = [260, 220];
const SPIRAL = squareSpiral(CENTER, 150, 12, 13);

const LABELS = [
  { label: "Regulations", pointIndex: 0 },
  { label: "Requirements", pointIndex: 2 },
  { label: "Policies", pointIndex: 4 },
  { label: "Controls", pointIndex: 6 },
  { label: "Evidence", pointIndex: 8 },
  { label: "Risks", pointIndex: 10 },
  { label: "Audits", pointIndex: 12 },
];

/**
 * Brief section 6, SectionLabyrinth: unlike the hero (which plays once on
 * load), this reveal is gently scroll-scrubbed — the visual should feel
 * like the visitor is *causing* it by scrolling, not watching an autoplay.
 * Both the thread draw and the label fade-in scrub against the same
 * ScrollTrigger, at the same pace, so they read as one continuous reveal
 * rather than two separately-timed effects.
 */
export default function SectionLabyrinth() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const pathRef = useRef<SVGPathElement>(null);

  useGSAP(
    () => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const labels = gsap.utils.toArray<SVGGElement>(".labyrinth-label");

      if (reducedMotion) {
        gsap.set(labels, { opacity: 1 });
        if (pathRef.current) gsap.set(pathRef.current, { drawSVG: "100%" });
        return;
      }

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: wrapperRef.current,
          start: "top 80%",
          end: "bottom 60%",
          scrub: true,
        },
      });

      if (pathRef.current) {
        tl.fromTo(pathRef.current, { drawSVG: "0%" }, { drawSVG: "100%", ease: "none" });
      }
      tl.fromTo(labels, { opacity: 0 }, { opacity: 1, stagger: 0.06, ease: "none" }, 0.15);
    },
    { scope: wrapperRef },
  );

  return (
    <section id="labyrinth" className="font-landing-sans mx-auto w-full max-w-6xl px-4 py-28 sm:px-8">
      <div className="grid gap-14 lg:grid-cols-2 lg:gap-20">
        <div>
          <Eyebrow>The labyrinth</Eyebrow>
          <h2 className="font-landing-serif mt-4 text-3xl leading-tight font-normal text-landing-fg sm:text-4xl">
            Compliance was never meant to be simple.
          </h2>
          <p className="mt-5 leading-relaxed text-landing-fg/70">
            Regulations, requirements, policies, controls, evidence, risks, audits — an
            organization doesn&apos;t lack information. It lacks a way through it.
          </p>
          <p className="mt-4 leading-relaxed text-landing-fg">
            The challenge isn&apos;t finding information. It&apos;s finding the path through it.
          </p>
        </div>
        <div ref={wrapperRef} className="flex items-center justify-center py-6">
          <svg
            viewBox="0 0 520 440"
            className="h-auto w-full max-w-md text-landing-border"
            role="img"
            aria-label="An abstract labyrinth with compliance domains — regulations, requirements, policies, controls, evidence, risks, and audits — at its nodes"
          >
            <path
              ref={pathRef}
              d={SPIRAL.d}
              fill="none"
              className="stroke-landing-thread"
              strokeWidth={1.3}
              strokeLinejoin="round"
            />
            {LABELS.map((item) => {
              const [x, y] = SPIRAL.points[item.pointIndex];
              return (
                <g key={item.label} className="labyrinth-label">
                  <rect
                    x={x - 2}
                    y={y - 12}
                    width={item.label.length * 6.4 + 14}
                    height={18}
                    rx={2}
                    className="fill-landing-surface stroke-landing-border"
                    strokeWidth={1}
                  />
                  <text
                    x={x + item.label.length * 3.2 + 5}
                    y={y + 1}
                    textAnchor="middle"
                    className="fill-landing-fg/70"
                    style={{ fontSize: 10, letterSpacing: "0.02em" }}
                  >
                    {item.label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </section>
  );
}

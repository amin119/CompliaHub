"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";

const STAGES = [
  {
    label: "Classify",
    body: "Every question is routed to the cheapest reasoning it actually needs — not every path gets the full loop.",
    icon: (
      <path
        d="M12 2v3m0 14v3M4.2 4.2l2.1 2.1m11.4 11.4 2.1 2.1M2 12h3m14 0h3M4.2 19.8l2.1-2.1m11.4-11.4 2.1-2.1"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    ),
  },
  {
    label: "Retrieve",
    body: "Dense and lexical search run together over every ingested clause, fused rather than trusting one signal alone.",
    icon: (
      <>
        <circle cx="10" cy="10" r="6.5" stroke="currentColor" strokeWidth="1.4" />
        <path d="m19 19-4.3-4.3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </>
    ),
  },
  {
    label: "Critique & Refine",
    body: "Its own evidence is weighed before answering — insufficient evidence triggers a rewritten search, within a budget.",
    icon: (
      <path
        d="M12 3v18M5 7l-3 6a3 3 0 0 0 6 0l-3-6Zm14 0-3 6a3 3 0 0 0 6 0l-3-6ZM5 7h14"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
  {
    label: "Ground",
    body: "The final answer is written only from what was found, with every claim traceable to its source clause.",
    icon: (
      <path
        d="m4 12 5 5L20 6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
];

/**
 * Section 4's "converging paths" visual — deliberately depicts the real
 * architecture (one classifier routing to real reasoning stages) rather
 * than the brief's example of named agent personas (Retrieval Agent,
 * Compliance Agent, Risk Agent, Verification Agent): those don't exist as
 * separate components in this system, and inventing them would misstate
 * what's actually built. Same "orchestrator with converging paths" visual
 * idea, honest labels.
 *
 * The four paths draw in via a scroll-scrubbed DrawSVG timeline (brief
 * section 6: "reveal the paths converging as the user scrolls through"),
 * not on mount.
 */
export default function OrchestrationPaths() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const paths = gsap.utils.toArray<SVGPathElement>(".orchestration-path");
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      if (reducedMotion) {
        gsap.set(paths, { drawSVG: "100%" });
        return;
      }

      gsap.fromTo(
        paths,
        { drawSVG: "0%" },
        {
          drawSVG: "100%",
          stagger: 0.1,
          ease: "none",
          scrollTrigger: {
            trigger: containerRef.current,
            start: "top 80%",
            end: "bottom 65%",
            scrub: true,
          },
        },
      );
    },
    { scope: containerRef },
  );

  return (
    <div ref={containerRef}>
      <svg viewBox="0 0 800 170" className="mb-4 h-auto w-full text-landing-border" aria-hidden="true">
        <circle cx="400" cy="14" r="5" className="fill-landing-accent" />
        <text
          x="400"
          y="38"
          textAnchor="middle"
          className="fill-landing-accent"
          style={{ fontSize: 11, letterSpacing: "0.2em", textTransform: "uppercase" }}
        >
          Orchestrator
        </text>
        {[100, 300, 500, 700].map((x) => (
          <path
            key={x}
            className="orchestration-path"
            d={`M 400 20 C 400 80, ${x} 55, ${x} 152`}
            fill="none"
            stroke="currentColor"
            strokeWidth={1}
          />
        ))}
      </svg>
      <div className="grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-4">
        {STAGES.map((stage) => (
          <div key={stage.label} className="text-center">
            <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full border border-landing-border bg-landing-surface text-landing-accent">
              <svg viewBox="0 0 24 24" fill="none" className="h-4.5 w-4.5">
                {stage.icon}
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-landing-fg">{stage.label}</h3>
            <p className="mt-2 text-xs leading-relaxed text-landing-fg/60">{stage.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

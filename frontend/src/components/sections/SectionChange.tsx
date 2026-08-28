"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";
import Eyebrow from "./Eyebrow";
import KnowledgeGraph, { NODE_BY_ID } from "@/components/landing/KnowledgeGraph";

/**
 * Brief section 9: reuses Section 8's map and animates a new node
 * appearing, a connection changing, and a risk node highlighting —
 * "communicates continuous monitoring without a generic analytics
 * dashboard." Deliberately does NOT claim automatic change-detection or
 * impact-analysis (not a real capability of this system — it ingests
 * documents on request, it doesn't monitor regulatory sources or diff
 * versions); the copy describes what's actually true instead: a
 * re-ingested document rejoins the same graph immediately.
 *
 * The "new requirement" node/link is passed to `KnowledgeGraph` as an
 * `overlay` rendered inside its own `<svg>`/viewBox, not a second,
 * separately-positioned SVG on top of it — the map's own wrapper also
 * includes a legend below the graph, so an absolutely-positioned overlay
 * sized to the whole wrapper would not align with the graph's own
 * coordinates.
 */
export default function SectionChange() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const newNode = containerRef.current?.querySelector(".change-new-node");
      const newLink = containerRef.current?.querySelector(".change-new-link");
      const riskNode = containerRef.current?.querySelector('[data-node-id="risk"] circle');

      if (!newNode || !newLink || !riskNode) return;

      if (reducedMotion) {
        gsap.set([newNode, newLink], { opacity: 1 });
        return;
      }

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top 75%",
          end: "bottom 60%",
          scrub: true,
        },
      });

      tl.fromTo(newLink, { opacity: 0 }, { opacity: 1, ease: "none" })
        .fromTo(newNode, { opacity: 0, scale: 0 }, { opacity: 1, scale: 1, ease: "none" }, "<")
        .to(riskNode, { scale: 1.5, ease: "none" }, "<0.3")
        .to(riskNode, { scale: 1, ease: "none" });
    },
    { scope: containerRef },
  );

  const risk = NODE_BY_ID.get("risk")!;
  const newX = risk.x + 70;
  const newY = risk.y - 55;

  return (
    <section className="font-landing-sans mx-auto w-full max-w-4xl px-4 pb-28 text-center sm:px-8">
      <Eyebrow>What changes, changes here too</Eyebrow>
      <h2 className="font-landing-serif mt-4 text-3xl leading-tight font-normal text-landing-fg sm:text-4xl">
        The labyrinth keeps changing.
      </h2>
      <p className="mx-auto mt-5 max-w-xl leading-relaxed text-landing-fg/70">
        Standards get revised. Policies get rewritten. Add the new version, and it becomes part
        of the same connected graph immediately — nothing about how you ask questions has to
        change.
      </p>
      <div ref={containerRef} className="mt-14">
        <KnowledgeGraph
          overlay={
            <>
              <line
                className="change-new-link"
                x1={risk.x}
                y1={risk.y}
                x2={newX}
                y2={newY}
                stroke="currentColor"
                strokeWidth={1}
              />
              <g className="change-new-node">
                <circle cx={newX} cy={newY} r={5} className="fill-landing-accent" />
                <text
                  x={newX}
                  y={newY - 11}
                  textAnchor="middle"
                  className="fill-landing-accent"
                  style={{ fontSize: 9.5, letterSpacing: "0.03em" }}
                >
                  New requirement
                </text>
              </g>
            </>
          }
        />
      </div>
    </section>
  );
}

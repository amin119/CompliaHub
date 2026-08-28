"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";
import Eyebrow from "./Eyebrow";
import BrowserFrame from "@/components/landing/BrowserFrame";
import DemoCitation from "@/components/landing/DemoCitation";

const CALLOUTS = [
  { label: "Live reasoning status", target: "status" },
  { label: "Citations, not just prose", target: "citation" },
  { label: "Real streamed tokens", target: "answer" },
];

/**
 * Brief section 11: a more detailed showcase than SectionIngestion/
 * SectionAsk's lighter teasers — editorial annotations and callout lines
 * pointing at specific real UI elements, plus a subtle zoom-on-scroll.
 * Same disclosed limitation as those two sections: no real screenshot or
 * recording was provided, so this is built from the real product's own
 * classes/copy, not a fabricated interface.
 */
export default function SectionProduct() {
  const frameRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reducedMotion) return;

      gsap.fromTo(
        frameRef.current,
        { scale: 0.96 },
        {
          scale: 1,
          ease: "none",
          scrollTrigger: {
            trigger: frameRef.current,
            start: "top 85%",
            end: "top 45%",
            scrub: true,
          },
        },
      );
    },
    { scope: frameRef },
  );

  return (
    <section className="font-landing-sans mx-auto w-full max-w-4xl px-4 py-28 sm:px-8">
      <div className="mb-14 text-center">
        <Eyebrow>The existing platform</Eyebrow>
        <h2 className="font-landing-serif mt-4 text-3xl leading-tight font-normal text-landing-fg sm:text-4xl">
          See it, in detail.
        </h2>
      </div>

      <div className="grid gap-8 lg:grid-cols-[1fr_220px] lg:items-center">
        <div ref={frameRef}>
          <BrowserFrame path="/chat">
            <div className="flex flex-col gap-3">
              <div className="ml-auto max-w-[75%] rounded-2xl rounded-br-md bg-landing-accent px-4 py-2.5 text-sm text-landing-accent-fg">
                What controls mitigate the risk of unauthorized access?
              </div>
              <div
                data-callout="status"
                className="mr-auto flex items-center gap-2 rounded-2xl rounded-bl-md bg-landing-surface px-4 py-2 text-xs text-landing-fg/60"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-landing-accent" />
                Retrieving evidence…
              </div>
              <div
                data-callout="answer"
                className="mr-auto max-w-[85%] rounded-2xl rounded-bl-md bg-landing-surface px-4 py-2.5 text-sm text-landing-fg"
              >
                Access control requires role-based provisioning, periodic review, and logging of
                privileged actions.
                <div
                  data-callout="citation"
                  className="mt-2.5 flex flex-wrap gap-1.5 border-t border-landing-border/60 pt-2.5"
                >
                  <DemoCitation
                    label="A.5.15 · iso-27001-2022.pdf"
                    title="iso-27001-2022.pdf"
                    excerpt="Access to information and other associated assets shall be limited in accordance with the established topic-specific policy on access control."
                  />
                </div>
              </div>
            </div>
          </BrowserFrame>
        </div>
        <ul className="flex flex-col gap-6">
          {CALLOUTS.map((callout) => (
            <li key={callout.target} className="flex items-center gap-3 text-left">
              <span className="h-px w-6 shrink-0 bg-landing-thread" aria-hidden="true" />
              <span className="text-xs leading-snug text-landing-fg/70">{callout.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

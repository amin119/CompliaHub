import Eyebrow from "./Eyebrow";
import InteractiveChain from "@/components/landing/InteractiveChain";

/**
 * Brief section 6, SectionThread: each node is a real focusable/hoverable
 * target revealing a real one-line detail — this is exactly the kind of
 * "discrete, component-level interaction that doesn't need GSAP's full
 * timeline machinery" the brief's own tech-stack table (section 1)
 * reserves for `motion`. `InteractiveChain` already does this (built in
 * Part 5), so it's reused here rather than rebuilt on GSAP for its own
 * sake.
 */
export default function SectionThread() {
  return (
    <section id="thread" className="font-landing-sans mx-auto w-full max-w-4xl px-4 py-28 sm:px-8">
      <div className="mb-16 text-center">
        <Eyebrow>The thread</Eyebrow>
        <h2 className="font-landing-serif mt-4 text-3xl leading-tight font-normal text-landing-fg sm:text-4xl">
          Follow the thread.
        </h2>
        <p className="mx-auto mt-5 max-w-xl leading-relaxed text-landing-fg/70">
          Hover each point. This is what an agentic pass over your documents actually produces —
          not a single similarity score, a path.
        </p>
      </div>
      <InteractiveChain />
    </section>
  );
}

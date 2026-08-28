import Eyebrow from "./Eyebrow";
import OrchestrationPaths from "@/components/landing/OrchestrationPaths";

export default function SectionAgents() {
  return (
    <section className="font-landing-sans mx-auto w-full max-w-4xl px-4 pb-28 sm:px-8">
      <div className="mb-14 text-center">
        <Eyebrow>Guided, not manual</Eyebrow>
        <h2 className="font-landing-serif mt-4 text-3xl leading-tight font-normal text-landing-fg sm:text-4xl">
          The thread isn&apos;t drawn by hand.
        </h2>
        <p className="mx-auto mt-5 max-w-xl leading-relaxed text-landing-fg/70">
          One orchestrating layer decides how much reasoning a question needs, then routes it
          through the stages that actually apply.
        </p>
      </div>
      <OrchestrationPaths />
    </section>
  );
}

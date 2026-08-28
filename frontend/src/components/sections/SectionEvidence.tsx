import Eyebrow from "./Eyebrow";
import Thread from "@/components/landing/Thread";
import DemoCitation from "@/components/landing/DemoCitation";

const CITATION = {
  label: "Article 32 · GDPR (EU) 2016/679",
  title: "GDPR (EU) 2016/679",
  excerpt:
    "Taking into account the state of the art... the controller and processor shall implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk.",
};

/**
 * Brief section 7, flagged as one of the most important sections: the
 * thread visually connects the answer to its source, using the exact same
 * `<Thread />` primitive (and DrawSVG technique) as the hero and every
 * other section — so a visitor recognizes this as "the same thread,"
 * doing its real job here rather than as ambient decoration. Only real
 * `Citation` fields shown (document, clause, excerpt) — no fabricated
 * page number, date, or jurisdiction.
 */
export default function SectionEvidence() {
  return (
    <section id="evidence" className="font-landing-sans mx-auto w-full max-w-2xl px-4 py-28 sm:px-8">
      <div className="mb-14 text-center">
        <Eyebrow>Evidence</Eyebrow>
        <h2 className="font-landing-serif mt-4 text-3xl leading-tight font-normal text-landing-fg sm:text-4xl">
          No black boxes. Just paths you can inspect.
        </h2>
        <p className="mx-auto mt-5 max-w-xl leading-relaxed text-landing-fg/70">
          An answer is only as trustworthy as what it points to. Every claim carries a thread
          back to the exact clause it came from.
        </p>
      </div>

      <div className="rounded-sm border border-landing-border bg-landing-surface p-7">
        <p className="text-sm leading-relaxed text-landing-fg">
          Article 32 requires &ldquo;appropriate technical and organisational measures&rdquo;
          proportionate to risk — encryption, resilience, and regular testing among them.
        </p>
      </div>
      <div className="mx-auto w-px">
        <Thread d="M 0 0 L 0 48" viewBox="0 0 1 48" className="mx-auto h-12 w-px" trigger="scroll" />
      </div>
      <div className="flex justify-center border-t border-landing-border pt-5">
        <DemoCitation {...CITATION} />
      </div>
    </section>
  );
}

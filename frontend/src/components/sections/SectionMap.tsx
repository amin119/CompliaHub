import Eyebrow from "./Eyebrow";
import KnowledgeGraph from "@/components/landing/KnowledgeGraph";

export default function SectionMap() {
  return (
    <section className="font-landing-sans mx-auto w-full max-w-4xl px-4 pb-28 text-center sm:px-8">
      <Eyebrow>The knowledge map</Eyebrow>
      <h2 className="font-landing-serif mt-4 text-3xl leading-tight font-normal text-landing-fg sm:text-4xl">
        Mapping a world that has no map.
      </h2>
      <div className="mt-14">
        <KnowledgeGraph />
      </div>
    </section>
  );
}

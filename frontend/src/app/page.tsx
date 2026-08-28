import SmoothScroll from "@/components/landing/SmoothScroll";
import Nav from "@/components/sections/Nav";
import Hero from "@/components/sections/Hero";
import SectionLabyrinth from "@/components/sections/SectionLabyrinth";
import SectionThread from "@/components/sections/SectionThread";
import SectionAgents from "@/components/sections/SectionAgents";
import SectionIngestion from "@/components/sections/SectionIngestion";
import SectionAsk from "@/components/sections/SectionAsk";
import SectionEvidence from "@/components/sections/SectionEvidence";
import SectionMap from "@/components/sections/SectionMap";
import SectionChange from "@/components/sections/SectionChange";
import SectionClarity from "@/components/sections/SectionClarity";
import SectionProduct from "@/components/sections/SectionProduct";
import SectionAudience from "@/components/sections/SectionAudience";
import SectionFinal from "@/components/sections/SectionFinal";
import Footer from "@/components/sections/Footer";

/**
 * Phase 1 of the GSAP/Lenis rebuild (see docs/phase-6-frontend.md's Part 7
 * for the full phase log). This composition is the "base layout shell" —
 * every section renders its real, final copy, but almost all of them are
 * static placeholders for now. Phases 2-5 replace each stub in place with
 * its real GSAP-driven behavior; nothing here is throwaway scaffolding
 * that gets deleted later, it's the actual page being built up in phases.
 */
export default function LandingPage() {
  return (
    <SmoothScroll>
      <div className="font-landing-sans relative flex min-h-screen flex-col bg-landing-bg text-landing-fg">
        <Nav />
        <Hero />
        <SectionLabyrinth />
        <SectionThread />
        <SectionAgents />
        <SectionIngestion />
        <SectionAsk />
        <SectionEvidence />
        <SectionMap />
        <SectionChange />
        <SectionClarity />
        <SectionProduct />
        <SectionAudience />
        <SectionFinal />
        <Footer />
      </div>
    </SmoothScroll>
  );
}

import SmoothScroll from "@/components/landing/SmoothScroll";
import Marquee from "@/components/landing/Marquee";
import Nav from "@/components/sections/Nav";
import Hero from "@/components/sections/Hero";
import SectionDemo from "@/components/sections/SectionDemo";
import SectionShowcase from "@/components/sections/SectionShowcase";
import SectionFeatures from "@/components/sections/SectionFeatures";
import SectionUseCases from "@/components/sections/SectionUseCases";
import SectionFinalCta from "@/components/sections/SectionFinalCta";
import Footer from "@/components/sections/Footer";

/**
 * Rebuilt to match a reference design supplied by the user (home page
 * design/home page.svg + .png — a job-matching platform called "Sahali"):
 * same structure, same visual language (gradient, marquee bands, rounded
 * cards, pill buttons), content adapted to this platform. See
 * docs/phase-6-frontend.md's Part 8 for the full list of adaptations —
 * every place the reference relied on something this platform doesn't
 * have (email capture, mobile app store badges, marketing stats, social
 * links) was replaced with something real rather than faked.
 */
export default function LandingPage() {
  return (
    <SmoothScroll>
      <div className="relative flex min-h-screen flex-col text-foreground">
        {/* One page-level ambient glow (top pink wash + bottom-corner
            pink/blue pastels in light mode, a single subdued green wash
            in dark mode — see globals.css's --glow-* tokens). Sits behind
            every section; the middle sections each carry their own opaque
            bg-background to occlude it, exactly like the reference design
            (glow only visible right behind the hero and right above the
            footer, plain white in between). */}
        <div aria-hidden="true" className="bg-ambient-glow pointer-events-none absolute inset-0 -z-10" />
        <Nav />
        <Hero />
        <Marquee text="THE FUTURE OF COMPLIANCE" />
        <div className="bg-background">
          <SectionDemo />
          <SectionShowcase />
          <SectionFeatures />
          <SectionUseCases />
        </div>
        <SectionFinalCta />
        <Marquee text="GROUNDED IN EVIDENCE" />
        <Footer />
      </div>
    </SmoothScroll>
  );
}

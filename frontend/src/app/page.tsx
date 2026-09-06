import SmoothScroll from "@/components/landing/SmoothScroll";
import Cursor from "@/components/landing/Cursor";
import Marquee from "@/components/landing/Marquee";
import Noise from "@/components/Noise";
import Nav from "@/components/sections/Nav";
import Hero from "@/components/sections/Hero";
import SectionDemo from "@/components/sections/SectionDemo";
import SectionScanner from "@/components/sections/SectionScanner";
import SectionShowcase from "@/components/sections/SectionShowcase";
import SectionFeatures from "@/components/sections/SectionFeatures";
import SectionUseCases from "@/components/sections/SectionUseCases";
import SectionFinalCta from "@/components/sections/SectionFinalCta";
import Footer from "@/components/sections/Footer";

/**
 * The landing page, ordered so both halves of the product are visible before
 * the fold and again at the close. The scanner section is the fix for a real
 * content gap: until this redesign, nothing on `/` mentioned the Compliance
 * Scanner at all, so half the platform was undiscoverable from the home page.
 *
 * Order: Ask (SectionDemo) → Scan (SectionScanner) → how retrieval works →
 * what it can do → what people use it for → close.
 *
 * `Cursor` and `Noise` are landing-only. The app runs in the quiet register —
 * see DESIGN-SYSTEM.md's two-register principle.
 */
export default function LandingPage() {
  return (
    <SmoothScroll>
      <Noise />
      <Cursor />
      <div className="relative flex min-h-screen flex-col text-foreground">
        <Nav />
        <Hero />
        <Marquee
          items={[
            "ISO 27001",
            "GDPR",
            "AI governance",
            "cited answers",
            "mapped findings",
            "human-in-the-loop review",
          ]}
        />
        <SectionDemo />
        <SectionScanner />
        <SectionShowcase />
        <SectionFeatures />
        <Marquee
          reverse
          items={[
            "upload a repo",
            "scan it",
            "map every finding",
            "suggest a fix",
            "have a person sign off",
          ]}
        />
        <SectionUseCases />
        <SectionFinalCta />
        <Footer />
      </div>
    </SmoothScroll>
  );
}

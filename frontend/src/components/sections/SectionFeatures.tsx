import Link from "next/link";
import Eyebrow from "./Eyebrow";
import Logo from "@/components/Logo";
import Reveal from "@/components/landing/Reveal";
import AnimatedConversation from "@/components/landing/AnimatedConversation";

/**
 * The reference design pairs a headline with two marketing stats ("32k
 * Trusted job recruiter", "1200+ Best Partner") — this platform has no
 * such numbers to report, and inventing them would be exactly the kind
 * of fabricated statistic this project has consistently refused to ship.
 * The two stat slots are kept (matching the reference's layout) but filled
 * with real, verifiable architectural facts instead of marketing numbers.
 */
const STATS = [
  { value: "3", label: "Retrieval strategies" },
  { value: "100%", label: "Answers cite a source" },
];

export default function SectionFeatures() {
  return (
    <section id="features" className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-8">
      <div className="grid items-center gap-14 lg:grid-cols-2">
        <Reveal>
          <Eyebrow>Features</Eyebrow>
          <h2 className="font-display mt-3 text-3xl leading-tight font-bold text-foreground sm:text-4xl">
            Get grounded answers, not guesses
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted">
            Every response streams back live as the system retrieves, checks its own evidence,
            and grounds the final answer — you can watch it reason.
          </p>
          <div className="mt-6 flex items-center gap-8">
            {STATS.map((stat, i) => (
              <div key={stat.label} className={i > 0 ? "border-l border-surface-border pl-8" : ""}>
                <p className="font-display text-2xl font-bold text-foreground">
                  {stat.value}
                </p>
                <p className="text-xs text-muted">{stat.label}</p>
              </div>
            ))}
          </div>
          <Link
            href="/chat"
            className="mt-7 inline-block rounded-full bg-cta px-7 py-3.5 text-sm font-semibold text-accent-foreground shadow-sm transition-transform hover:scale-105"
          >
            Try it now
          </Link>
        </Reveal>

        <AnimatedConversation className="flex flex-col gap-4">
          <div className="flex items-end gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface">
              <Logo className="h-4 w-4 text-accent" />
            </span>
            <div className="max-w-[80%] rounded-3xl rounded-bl-md bg-surface px-4 py-2.5 text-sm text-foreground">
              Hi! I&apos;m interested in whether our access control policy meets ISO 27001.
            </div>
          </div>
          <div className="ml-auto flex items-end gap-2">
            <div className="max-w-[80%] rounded-3xl rounded-br-md bg-cta px-4 py-2.5 text-sm text-white">
              Annex A.5.15 requires role-based access limited to what&apos;s necessary — I can
              check your current policy against it.
            </div>
            <span className="h-8 w-8 shrink-0 rounded-full bg-surface-blue" />
          </div>
        </AnimatedConversation>
      </div>
    </section>
  );
}

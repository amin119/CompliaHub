"use client";

import { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import BrowserFrame from "@/components/landing/BrowserFrame";
import MagneticLink from "@/components/landing/MagneticLink";
import RevealText from "@/components/landing/RevealText";
import Reveal from "@/components/landing/Reveal";
import FindingStatusBadge from "@/components/FindingStatusBadge";
import SeverityBadge from "@/components/SeverityBadge";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { ScrollTrigger } from "@/lib/gsap";
import { buttonClasses } from "@/lib/ui";

/**
 * The half of the product the marketing page never mentioned. Everything
 * claimed here is a capability the scanner actually has — see the
 * `docs/scanner-phase-*.md` build log.
 *
 * The pipeline is genuinely a sequence, which is the one place numbered
 * markers earn their keep in this design (the retired `Eyebrow` label was
 * decorative; these encode real order). It's the only scroll-pinned section
 * on the Scan half of the page.
 */

const STEPS = [
  {
    id: "upload",
    title: "Upload",
    body: "Drop in a .zip of the repository. CompliaHub extracts and classifies every file it can read.",
  },
  {
    id: "scan",
    title: "Scan",
    body: "Deterministic rules — no LLM involved — flag secrets, weak crypto, hardcoded credentials and insecure config.",
  },
  {
    id: "map",
    title: "Map",
    body: "Every finding is mapped onto real ISO 27001 Annex A controls, alongside GDPR and AI-governance checks.",
  },
  {
    id: "validate",
    title: "Validate",
    body: "An AI pass grounds each finding against your ingested standards and says whether it holds up. It can never change a finding's status.",
  },
  {
    id: "remediate",
    title: "Remediate",
    body: "Ask for a fix and get a unified diff against the real file — yours to review and apply, never applied for you.",
  },
  {
    id: "review",
    title: "Review",
    body: "A person confirms or rejects each finding with a written justification. Only a human can mark something verified.",
  },
  {
    id: "report",
    title: "Report",
    body: "A printable evidence report: severity, status, framework coverage, and who reviewed what.",
  },
];

function Panel({ step }: { step: number }) {
  switch (STEPS[step].id) {
    case "upload":
      return (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-surface-border bg-surface py-12 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-accent-soft text-accent">
            <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5">
              <path
                d="M10 14V4m0 0L6.5 7.5M10 4l3.5 3.5M4 15v1.5h12V15"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <p className="text-sm text-foreground">payments-service.zip</p>
          <p className="text-xs text-muted">62 files, Python and FastAPI detected</p>
        </div>
      );

    case "scan":
      return (
        <div className="flex flex-col gap-2.5">
          {[
            { severity: "HIGH", title: "Weak hash algorithm", file: "app/auth.py:42" },
            { severity: "MEDIUM", title: "Debug mode enabled", file: "app/config.py:8" },
            { severity: "LOW", title: "Unpinned dependency", file: "requirements.txt" },
          ].map((finding) => (
            <div
              key={finding.title}
              className="flex items-center gap-3 rounded-2xl border border-surface-border bg-surface px-3.5 py-2.5"
            >
              <SeverityBadge severity={finding.severity} />
              <div className="min-w-0">
                <p className="truncate text-sm text-foreground">{finding.title}</p>
                <p className="truncate text-xs text-muted">{finding.file}</p>
              </div>
            </div>
          ))}
        </div>
      );

    case "map":
      return (
        <div className="flex flex-col gap-3">
          <div className="rounded-2xl border border-surface-border bg-surface px-4 py-3">
            <p className="text-sm text-foreground">Weak hash algorithm</p>
            <p className="mt-1 text-xs text-muted">app/auth.py:42 — hashlib.md5()</p>
          </div>
          <div className="flex justify-center text-muted">
            <svg viewBox="0 0 16 16" fill="none" className="h-5 w-5">
              <path
                d="M8 3v10m0 0 3.5-3.5M8 13 4.5 9.5"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div className="rounded-2xl border border-accent/30 bg-accent-soft px-4 py-3">
            <p className="text-sm font-medium text-accent">ISO 27001 A.8.24</p>
            <p className="mt-1 text-xs text-muted">Use of cryptography</p>
          </div>
        </div>
      );

    case "validate":
      return (
        <div className="rounded-2xl border border-ai/30 bg-ai-soft p-4">
          <p className="text-xs font-medium text-ai">AI validation</p>
          <p className="mt-2 text-sm leading-relaxed text-foreground">
            The retrieved control text on cryptographic key management supports this concern.
            MD5 is unsuitable for password hashing.
          </p>
          <p className="mt-3 text-xs text-muted">
            Grounded in A.8.24 of your ingested ISO 27001 document.
          </p>
        </div>
      );

    case "remediate":
      return (
        <div className="overflow-hidden rounded-2xl border border-surface-border bg-surface">
          <p className="border-b border-surface-border px-4 py-2 text-xs text-muted">
            app/auth.py
          </p>
          <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed">
            <code>
              <span className="block text-muted">{"  import hashlib"}</span>
              <span className="block text-red-600 dark:text-red-400">
                {"- return hashlib.md5(pw.encode()).hexdigest()"}
              </span>
              <span className="block text-emerald-700 dark:text-emerald-400">
                {"+ return bcrypt.hashpw(pw.encode(), bcrypt.gensalt())"}
              </span>
            </code>
          </pre>
        </div>
      );

    case "review":
      return (
        <div className="flex flex-col gap-3 rounded-2xl border border-surface-border bg-surface p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-foreground">Weak hash algorithm</p>
            <FindingStatusBadge status="VERIFIED" />
          </div>
          <div className="rounded-xl border border-surface-border bg-surface-raised px-3 py-2.5 text-xs text-muted">
            <p className="text-foreground">Reviewed by A. Chabbah</p>
            <p className="mt-1 leading-relaxed">
              Confirmed against A.8.24. Fix applied in PR #412 and re-scanned.
            </p>
          </div>
        </div>
      );

    default:
      return (
        <div className="flex flex-col gap-4">
          <div className="flex items-baseline justify-between">
            <p className="font-display text-lg font-semibold text-foreground">Evidence report</p>
            <p className="text-xs text-muted">payments-service.zip</p>
          </div>
          {[
            { label: "Critical", value: 0, width: "4%" },
            { label: "High", value: 3, width: "38%" },
            { label: "Medium", value: 6, width: "70%" },
            { label: "Low", value: 4, width: "48%" },
          ].map((row) => (
            <div key={row.label} className="flex items-center gap-3 text-xs">
              <span className="w-14 shrink-0 text-muted">{row.label}</span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface">
                <span className="block h-full rounded-full bg-accent" style={{ width: row.width }} />
              </span>
              <span className="w-4 shrink-0 text-right text-foreground">{row.value}</span>
            </div>
          ))}
          <p className="border-t border-surface-border pt-3 text-xs leading-relaxed text-muted">
            Technical evidence coverage, not a certification or compliance score.
          </p>
        </div>
      );
  }
}

export default function SectionScanner() {
  const sectionRef = useRef<HTMLElement>(null);
  const pinRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef(0);
  const [active, setActive] = useState(0);

  // Read through `useMediaQuery` rather than calling `prefersReducedMotion()`
  // during render: that helper returns `false` on the server and the real
  // value on the client, which would be a genuine hydration mismatch for
  // anyone who has the preference set. `useSyncExternalStore` renders the
  // server snapshot first and corrects itself immediately after hydration.
  const reduced = useMediaQuery("(prefers-reduced-motion: reduce)");
  // A pinned block that's taller than the viewport hides part of itself for
  // the whole time it's pinned, with no way to scroll to it. Short viewports
  // get the unpinned list instead — the same fallback reduced motion gets.
  const tallEnough = useMediaQuery("(min-height: 760px)");
  const canPin = !reduced && tallEnough;

  useGSAP(
    () => {
      // Unpinned, the section renders as a plain ordered list with every
      // step's description open and one representative panel, so all of the
      // information is still there without any scroll hijacking.
      if (!canPin || !pinRef.current) return;

      const trigger = ScrollTrigger.create({
        trigger: pinRef.current,
        // Below the fixed nav rather than flush with the viewport top.
        start: "top 96px",
        end: `+=${STEPS.length * 260}`,
        pin: pinRef.current,
        scrub: true,
        onUpdate: (self) => {
          const index = Math.min(
            STEPS.length - 1,
            Math.floor(self.progress * STEPS.length),
          );
          // Guarded: onUpdate fires on every scroll frame, and setting the
          // same index repeatedly would re-render the panel dozens of times
          // a second for no reason.
          if (index !== activeRef.current) {
            activeRef.current = index;
            setActive(index);
          }
        },
      });

      return () => trigger.kill();
    },
    { scope: sectionRef, dependencies: [canPin] },
  );

  return (
    // scroll-mt clears the fixed nav when this section is jumped to from it —
    // without it the heading lands underneath the bar.
    <section id="how-it-works" ref={sectionRef} className="scroll-mt-24 bg-background">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-8 sm:py-24">
        <div className="max-w-3xl">
          <RevealText
            as="h2"
            className="font-display text-h2 font-semibold text-foreground"
          >
            Point it at your repo. Get an audit.
          </RevealText>
          <Reveal>
            <p className="measure text-lead mt-6 text-muted">
              Upload a .zip. CompliaHub scans it for security, GDPR and AI-governance issues,
              maps every finding to ISO 27001, suggests fixes, and hands you a printable
              evidence report.
            </p>
          </Reveal>
        </div>

        {/* The CTA is inside the pinned block on purpose: it stays on screen
            for the whole walkthrough, and it fills what would otherwise be
            dead space under a block much shorter than the viewport. */}
        <div ref={pinRef}>
          <div className="mt-12 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <ol className="flex flex-col gap-1">
              {STEPS.map((step, index) => {
                const isActive = canPin && index === active;
                // Pinned, only the current step's description is open — that
                // keeps the whole block short enough to never outgrow the
                // viewport it's pinned inside. Unpinned, every step is open.
                const showBody = !canPin || isActive;
                return (
                  <li
                    key={step.id}
                    className={`flex gap-4 rounded-2xl px-4 py-3 transition-colors duration-[var(--dur-base)] ${
                      isActive ? "bg-surface" : ""
                    }`}
                  >
                    <span
                      className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors duration-[var(--dur-base)] ${
                        isActive
                          ? "bg-mark text-mark-contrast"
                          : "border border-surface-border text-muted"
                      }`}
                    >
                      {index + 1}
                    </span>
                    <div className="min-w-0">
                      <p
                        className={`font-display text-base font-semibold transition-colors duration-[var(--dur-base)] ${
                          showBody ? "text-foreground" : "text-muted"
                        }`}
                      >
                        {step.title}
                      </p>
                      {/* A 0fr → 1fr grid row, so the description opens and
                          closes smoothly instead of snapping. */}
                      <div
                        className={`grid transition-[grid-template-rows] duration-[var(--dur-base)] ease-[var(--ease-out-quart)] ${
                          showBody ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
                        }`}
                      >
                        <p className="overflow-hidden text-sm leading-relaxed text-muted">
                          <span className="mt-1 block">{step.body}</span>
                        </p>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>

            <BrowserFrame path="compliahub.app/scanner">
              <div className="min-h-[260px]">
                <Panel step={canPin ? active : 1} />
              </div>
            </BrowserFrame>
          </div>

          <div className="mt-10">
            <MagneticLink
              href="/scanner"
              cursorLabel="Scan"
              className={buttonClasses({ size: "lg" })}
            >
              Scan a repo
            </MagneticLink>
          </div>
        </div>
      </div>
    </section>
  );
}

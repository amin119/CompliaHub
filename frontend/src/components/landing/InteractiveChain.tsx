"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";

const CHAIN = [
  {
    label: "Document",
    detail: "iso-27001-2022.pdf, clause 8.2 — parsed and chunked at ingestion.",
  },
  {
    label: "Requirement",
    detail: "“The organization shall perform information security risk assessments at planned intervals.”",
  },
  {
    label: "Control",
    detail: "Mapped to Annex A.5.7, Threat intelligence — the control this requirement is satisfied by.",
  },
  {
    label: "Evidence",
    detail: "The exact excerpt retrieval pulled, with its clause number and source document attached.",
  },
  {
    label: "Risk",
    detail: "Undetected threats accumulate without a periodic, planned assessment cycle.",
  },
  {
    label: "Answer",
    detail: "A grounded response, citing clause 8.2 directly — not a paraphrase of general knowledge.",
  },
];

/**
 * Section 3's "Follow the thread" — the brief asks for each point on the
 * chain to be interactive, revealing what it actually represents on
 * hover/focus. A real click target too (not hover-only), so it works on
 * touch devices and for keyboard navigation.
 *
 * Uses the landing-only `--landing-*` tokens (bronze for the thread line
 * itself, aegean accent for the active node) — this component lives under
 * `components/landing/`, never the app's own `--color-*`/`--accent`
 * tokens `/chat` and `/documents` depend on.
 */
export default function InteractiveChain() {
  const [active, setActive] = useState(0);

  return (
    <div>
      <div className="relative flex items-center justify-between">
        <div className="absolute top-1/2 right-0 left-0 -z-10 h-px -translate-y-1/2 bg-landing-thread/40" />
        {CHAIN.map((step, i) => (
          <button
            key={step.label}
            type="button"
            onMouseEnter={() => setActive(i)}
            onFocus={() => setActive(i)}
            onClick={() => setActive(i)}
            className="flex flex-col items-center gap-2 bg-landing-bg px-1"
          >
            <motion.span
              animate={{ scale: active === i ? 1.25 : 1 }}
              className={`h-2.5 w-2.5 rounded-full border ${
                active === i
                  ? "border-landing-accent bg-landing-accent"
                  : "border-landing-border bg-landing-surface"
              }`}
            />
            <span
              className={`text-[11px] font-medium tracking-wide sm:text-xs ${
                active === i ? "text-landing-accent" : "text-landing-fg/60"
              }`}
            >
              {step.label}
            </span>
          </button>
        ))}
      </div>
      <div className="mt-8 min-h-16 rounded-sm border border-landing-border bg-landing-surface p-5">
        <AnimatePresence mode="wait">
          <motion.p
            key={active}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.25 }}
            className="text-sm leading-relaxed text-landing-fg"
          >
            {CHAIN[active].detail}
          </motion.p>
        </AnimatePresence>
      </div>
    </div>
  );
}

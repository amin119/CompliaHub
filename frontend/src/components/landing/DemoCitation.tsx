"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";

/**
 * Visually identical to the real product's `CitationChip` (same classes,
 * same expand/collapse behavior) but never calls the API — the landing
 * page's evidence/chat-preview mockups use illustrative citations that
 * don't correspond to real ingested documents, so wiring them to
 * `CitationChip`'s real `GET /documents/{id}/chunks` fetch would just
 * surface a confusing error the moment a visitor clicked one.
 */
export default function DemoCitation({
  label,
  title,
  excerpt,
}: {
  label: string;
  title: string;
  excerpt: string;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="inline-block">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className={`rounded-sm border px-2.5 py-0.5 text-xs transition-colors ${
          expanded
            ? "border-landing-accent/40 bg-landing-accent-soft text-landing-accent"
            : "border-landing-border bg-landing-surface text-landing-fg/60 hover:border-landing-accent/40 hover:text-landing-accent"
        }`}
      >
        {label}
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-1.5 max-w-sm rounded-sm border border-landing-border bg-landing-bg p-2.5 text-xs text-landing-fg/80">
              <p className="mb-1 font-medium text-landing-fg/50">{title}</p>
              <p className="whitespace-pre-wrap">{excerpt}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

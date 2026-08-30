"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";

/**
 * Visually identical to the real product's `CitationChip` (same
 * expand/collapse behavior) but never calls the API — the landing page's
 * evidence/chat-preview mockups use illustrative citations that don't
 * correspond to real ingested documents, so wiring them to `CitationChip`'s
 * real `GET /documents/{id}/chunks` fetch would just surface a confusing
 * error the moment a visitor clicked one.
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
        className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
          expanded
            ? "border-accent/40 bg-accent-soft text-accent"
            : "border-surface-border bg-background text-muted hover:border-accent/40 hover:text-accent"
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
            <div className="mt-1.5 max-w-sm rounded-2xl border border-surface-border bg-surface p-3 text-xs text-foreground/80">
              <p className="mb-1 font-medium text-muted">{title}</p>
              <p className="whitespace-pre-wrap">{excerpt}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

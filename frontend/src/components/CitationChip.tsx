"use client";

import { useState } from "react";
import { getDocumentChunks, type Citation, type DocumentChunk } from "@/lib/api";

/**
 * The API has no single-chunk endpoint — fetching a citation's full clause
 * text means fetching the whole document's chunks and filtering client-side
 * by chunk_id. Cached per-click (not prefetched for every citation up
 * front) so a message with several citations from the same document only
 * pays for that fetch once the user actually asks to see one.
 */
export default function CitationChip({ citation }: { citation: Citation }) {
  const [expanded, setExpanded] = useState(false);
  const [chunk, setChunk] = useState<DocumentChunk | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleToggle() {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setExpanded(true);
    if (chunk || loading) return;

    setLoading(true);
    setError(null);
    try {
      const chunks = await getDocumentChunks(citation.document_id);
      const match = chunks.find((candidate) => candidate.id === citation.chunk_id);
      if (!match) {
        setError("Clause not found — the document may have been re-ingested.");
        return;
      }
      setChunk(match);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load clause.");
    } finally {
      setLoading(false);
    }
  }

  const label = citation.clause_number
    ? `${citation.clause_number} · ${citation.document_filename}`
    : citation.document_filename;

  return (
    <div className="inline-block">
      <button
        type="button"
        onClick={handleToggle}
        aria-expanded={expanded}
        className="rounded-full border border-zinc-300 bg-white px-2 py-0.5 text-xs text-zinc-600 hover:border-zinc-400 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
      >
        {label}
      </button>
      {expanded && (
        <div className="mt-1 max-w-sm rounded-lg border border-zinc-200 bg-zinc-50 p-2 text-xs text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
          {loading && <span className="text-zinc-400 dark:text-zinc-500">Loading…</span>}
          {error && <span className="text-red-600 dark:text-red-400">{error}</span>}
          {chunk && (
            <>
              <p className="mb-1 font-medium text-zinc-500 dark:text-zinc-500">
                {chunk.title ?? citation.document_filename}
              </p>
              <p className="whitespace-pre-wrap">{chunk.text}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

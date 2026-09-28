"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { uploadDocument, getDocument, type DocumentStatus } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import UploadDropzone from "@/components/UploadDropzone";
import PageHeader from "@/components/PageHeader";
import { CHIP_BASE } from "@/lib/ui";

const TERMINAL_STATUSES = ["ready", "failed"];
const POLL_INTERVAL_MS = 3000;

const listVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

/** A short, honest chip — the file's own extension, nothing inferred. */
function fileExtension(filename: string): string | null {
  const match = /\.([a-z0-9]+)$/i.exec(filename);
  return match ? match[1].toUpperCase() : null;
}

function DocumentIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <path
        d="M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5A1.5 1.5 0 0 1 7 3.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M14 3.5V7a1 1 0 0 0 1 1h3.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M9 13h6M9 16h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentStatus[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setUploading(true);
    setUploadError(null);
    try {
      const doc = await uploadDocument(file);
      setDocuments((prev) => {
        // Re-uploading the same file returns the same id (backend hash
        // dedup) — replace rather than duplicate if it's already listed.
        const withoutDuplicate = prev.filter((existing) => existing.id !== doc.id);
        return [doc, ...withoutDuplicate];
      });
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  // There's no "list all documents" endpoint (nor push/websocket updates),
  // so this only ever tracks documents uploaded this browser session, and
  // polls each in-flight one until both status and graph_status settle —
  // a real, honest limitation of the current API, not an oversight.
  useEffect(() => {
    const hasInFlightDocument = documents.some((doc) => !TERMINAL_STATUSES.includes(doc.status));
    if (!hasInFlightDocument) return;

    const timeoutId = setTimeout(async () => {
      const refreshed = await Promise.all(
        documents.map((doc) =>
          TERMINAL_STATUSES.includes(doc.status) ? doc : getDocument(doc.id).catch(() => doc),
        ),
      );
      setDocuments(refreshed);
    }, POLL_INTERVAL_MS);

    return () => clearTimeout(timeoutId);
  }, [documents]);

  return (
    <div className="flex flex-1 flex-col items-center bg-background">
      <div className="flex w-full max-w-2xl flex-1 flex-col px-4 py-6 sm:py-8">
        <PageHeader
          icon={<DocumentIcon className="h-5 w-5" />}
          title="Documents"
          description="Upload a PDF or DOCX standard to ingest it into the knowledge graph."
        />

        <UploadDropzone
          accept=".pdf,.docx"
          uploading={uploading}
          idleLabel="Click or drag a PDF/DOCX file"
          uploadingLabel="Parsing and ingesting…"
          hint="Chunked, embedded, and added to the knowledge graph"
          onFile={(file) => void handleFile(file)}
        />
        <AnimatePresence>
          {uploadError && (
            <motion.p
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4 overflow-hidden text-sm text-red-600 dark:text-red-400"
            >
              {uploadError}
            </motion.p>
          )}
        </AnimatePresence>

        {documents.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-surface-border py-12 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft text-accent ring-8 ring-accent-soft/40">
              <DocumentIcon className="h-6 w-6" />
            </span>
            <div>
              <p className="text-sm font-medium text-foreground">No documents yet</p>
              <p className="mt-0.5 text-sm text-muted">
                Uploaded standards will appear here, this session.
              </p>
            </div>
          </div>
        ) : (
          <>
            <p className="mb-3 text-xs font-medium text-muted">
              Uploaded this session ({documents.length})
            </p>
            <motion.ul
              className="flex flex-col gap-3"
              variants={listVariants}
              initial="hidden"
              animate="show"
            >
            <AnimatePresence initial={false}>
              {documents.map((doc) => (
                <motion.li
                  key={doc.id}
                  layout
                  variants={{
                    hidden: { opacity: 0, y: -8 },
                    show: { opacity: 1, y: 0 },
                  }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                  className="card-interactive rounded-2xl border border-surface-border bg-surface-raised p-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                      <DocumentIcon className="h-4.5 w-4.5" />
                    </div>
                    <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                      {doc.filename}
                    </span>
                    {fileExtension(doc.filename) && (
                      <span className={CHIP_BASE}>{fileExtension(doc.filename)}</span>
                    )}
                    <StatusBadge status={doc.status} />
                  </div>
                  {doc.status === "ready" && (
                    <div className="mt-3 flex items-center justify-between gap-2 border-t border-surface-border pt-3">
                      <span className="text-xs text-muted">Graph extraction</span>
                      <StatusBadge status={doc.graph_status} />
                    </div>
                  )}
                  {/* error_message can be stale from an earlier attempt that
                      later succeeded (a known backend quirk) — only trust it
                      while the corresponding status is genuinely "failed". */}
                  {doc.status === "failed" && doc.error_message && (
                    <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                      {doc.error_message}
                    </p>
                  )}
                  {doc.graph_status === "failed" && doc.graph_error_message && (
                    <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                      {doc.graph_error_message}
                    </p>
                  )}
                </motion.li>
              ))}
            </AnimatePresence>
            </motion.ul>
          </>
        )}
      </div>
    </div>
  );
}

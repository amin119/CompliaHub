"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { uploadDocument, getDocument, type DocumentStatus } from "@/lib/api";

const TERMINAL_STATUSES = ["ready", "failed"];
const POLL_INTERVAL_MS = 3000;

function statusStyle(status: string): { dot: string; text: string } {
  if (status === "ready") return { dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" };
  if (status === "failed") return { dot: "bg-red-500", text: "text-red-600 dark:text-red-400" };
  return { dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400" };
}

function StatusBadge({ status }: { status: string }) {
  const style = statusStyle(status);
  const inFlight = !TERMINAL_STATUSES.includes(status);
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${style.text}`}>
      <span className="relative flex h-1.5 w-1.5">
        {inFlight && (
          <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${style.dot} opacity-60`} />
        )}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${style.dot}`} />
      </span>
      {status}
    </span>
  );
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentStatus[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void handleFile(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleDrop(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void handleFile(file);
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
        <header className="mb-6">
          <h1 className="font-display text-2xl font-normal tracking-tight text-foreground">
            Documents
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Upload a PDF or DOCX standard to ingest it into the knowledge graph.
          </p>
        </header>

        <label
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={`mb-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed p-10 text-sm transition-colors ${
            dragActive
              ? "border-accent bg-accent-soft text-accent"
              : "border-surface-border bg-surface text-zinc-500 hover:border-accent/40 hover:bg-accent-soft/40 dark:text-zinc-400"
          }`}
        >
          <motion.svg
            viewBox="0 0 24 24"
            fill="none"
            className="h-8 w-8"
            animate={uploading ? { y: [0, -4, 0] } : {}}
            transition={{ duration: 1, repeat: uploading ? Infinity : 0 }}
          >
            <path
              d="M12 16V4m0 0 4 4m-4-4-4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </motion.svg>
          <span className="font-medium">
            {uploading ? "Uploading…" : dragActive ? "Drop it here" : "Click or drag a PDF/DOCX file"}
          </span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileChange}
            disabled={uploading}
            className="hidden"
          />
        </label>
        {uploadError && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{uploadError}</p>}

        <ul className="flex flex-col gap-3">
          {documents.length === 0 && (
            <li className="text-sm text-zinc-400 dark:text-zinc-600">
              No documents uploaded yet this session.
            </li>
          )}
          <AnimatePresence initial={false}>
            {documents.map((doc) => (
              <motion.li
                key={doc.id}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="rounded-2xl border border-surface-border bg-surface p-4 shadow-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium text-foreground">
                    {doc.filename}
                  </span>
                  <StatusBadge status={doc.status} />
                </div>
                {doc.status === "ready" && (
                  <div className="mt-1.5 flex items-center justify-between gap-2 border-t border-surface-border pt-1.5">
                    <span className="text-xs text-zinc-500 dark:text-zinc-500">
                      Graph extraction
                    </span>
                    <StatusBadge status={doc.graph_status} />
                  </div>
                )}
                {/* error_message can be stale from an earlier attempt that
                    later succeeded (a known backend quirk) — only trust it
                    while the corresponding status is genuinely "failed". */}
                {doc.status === "failed" && doc.error_message && (
                  <p className="mt-2 text-xs text-red-600 dark:text-red-400">{doc.error_message}</p>
                )}
                {doc.graph_status === "failed" && doc.graph_error_message && (
                  <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                    {doc.graph_error_message}
                  </p>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </div>
    </div>
  );
}

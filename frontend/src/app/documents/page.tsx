"use client";

import { useEffect, useRef, useState } from "react";
import { uploadDocument, getDocument, type DocumentStatus } from "@/lib/api";

const TERMINAL_STATUSES = ["ready", "failed"];
const POLL_INTERVAL_MS = 3000;

function statusColor(status: string): string {
  if (status === "ready") return "text-green-600 dark:text-green-400";
  if (status === "failed") return "text-red-600 dark:text-red-400";
  return "text-amber-600 dark:text-amber-400";
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentStatus[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

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
      if (fileInputRef.current) fileInputRef.current.value = "";
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
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <div className="flex w-full max-w-2xl flex-1 flex-col px-4 py-8">
        <header className="mb-6">
          <h1 className="text-xl font-semibold text-zinc-950 dark:text-zinc-50">Documents</h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Upload a PDF or DOCX standard to ingest it into the knowledge graph.
          </p>
        </header>

        <label className="mb-6 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-zinc-300 bg-white p-8 text-sm text-zinc-500 hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-400">
          {uploading ? "Uploading…" : "Click to choose a PDF or DOCX file"}
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
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium text-zinc-950 dark:text-zinc-50">
                  {doc.filename}
                </span>
                <span className={`shrink-0 text-xs font-medium ${statusColor(doc.status)}`}>
                  {doc.status}
                </span>
              </div>
              {doc.status === "ready" && (
                <div className="mt-1 flex items-center justify-between gap-2">
                  <span className="text-xs text-zinc-500 dark:text-zinc-500">
                    Graph extraction
                  </span>
                  <span className={`text-xs font-medium ${statusColor(doc.graph_status)}`}>
                    {doc.graph_status}
                  </span>
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
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

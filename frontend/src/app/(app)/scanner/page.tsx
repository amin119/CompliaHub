"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { uploadScan, getScan, listScans, type ScanStatus } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

const TERMINAL_STATUSES = ["ready", "failed"];
const POLL_INTERVAL_MS = 3000;

function formatSize(bytes: number | null): string {
  if (bytes === null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ScannerPage() {
  const [scans, setScans] = useState<ScanStatus[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Unlike /documents, `GET /scans` really exists — hydrate scan history
  // across sessions instead of only tracking what this tab uploaded.
  useEffect(() => {
    listScans()
      .then(setScans)
      .catch(() => {
        // A failed initial load just means an empty list — the upload
        // flow below still works standalone.
      });
  }, []);

  async function handleFile(file: File) {
    setUploading(true);
    setUploadError(null);
    try {
      const scan = await uploadScan(file);
      setScans((prev) => {
        // Re-uploading the same archive returns the same id (backend hash
        // dedup) — replace rather than duplicate if it's already listed.
        const withoutDuplicate = prev.filter((existing) => existing.id !== scan.id);
        return [scan, ...withoutDuplicate];
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

  useEffect(() => {
    const hasInFlightScan = scans.some((scan) => !TERMINAL_STATUSES.includes(scan.status));
    if (!hasInFlightScan) return;

    const timeoutId = setTimeout(async () => {
      const refreshed = await Promise.all(
        scans.map((scan) =>
          TERMINAL_STATUSES.includes(scan.status) ? scan : getScan(scan.id).catch(() => scan),
        ),
      );
      setScans(refreshed);
    }, POLL_INTERVAL_MS);

    return () => clearTimeout(timeoutId);
  }, [scans]);

  return (
    <div className="flex flex-1 flex-col items-center bg-background">
      <div className="flex w-full max-w-2xl flex-1 flex-col px-4 py-6 sm:py-8">
        <header className="mb-6">
          <h1 className="font-display text-2xl font-normal tracking-tight text-foreground">
            Scanner
          </h1>
          <p className="text-sm text-muted">
            Upload a repository (as a .zip) to inventory its languages, frameworks, and
            files — the foundation technical evidence for compliance analysis is drawn from.
            This is an evidence inventory, not a compliance verdict: nothing here claims your
            repository is or isn&apos;t compliant with any standard.
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
              : "border-surface-border bg-surface text-muted hover:border-accent/40 hover:bg-accent-soft/40"
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
            {uploading ? "Uploading…" : dragActive ? "Drop it here" : "Click or drag a .zip repository archive"}
          </span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            onChange={handleFileChange}
            disabled={uploading}
            className="hidden"
          />
        </label>
        {uploadError && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{uploadError}</p>}

        <ul className="flex flex-col gap-3">
          {scans.length === 0 && (
            <li className="text-sm text-muted">No repositories scanned yet.</li>
          )}
          <AnimatePresence initial={false}>
            {scans.map((scan) => (
              <motion.li
                key={scan.id}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <Link
                  href={`/scanner/${scan.id}`}
                  className="block rounded-2xl border border-surface-border bg-surface p-4 shadow-sm transition-colors hover:border-accent/40"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-foreground">
                      {scan.original_filename}
                    </span>
                    <StatusBadge status={scan.status} />
                  </div>
                  {scan.status === "ready" && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                      <span>{scan.file_count} files</span>
                      <span>{formatSize(scan.total_size_bytes)}</span>
                      {scan.detected_languages.slice(0, 4).map((language) => (
                        <span key={language} className="rounded-full bg-accent-soft px-2 py-0.5 text-accent">
                          {language}
                        </span>
                      ))}
                    </div>
                  )}
                  {scan.status === "failed" && scan.error_message && (
                    <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                      {scan.error_message}
                    </p>
                  )}
                </Link>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </div>
    </div>
  );
}

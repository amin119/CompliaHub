"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { uploadScan, getScan, listScans, type ScanStatus } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import UploadDropzone from "@/components/UploadDropzone";
import Skeleton from "@/components/Skeleton";

const TERMINAL_STATUSES = ["ready", "failed"];
const POLL_INTERVAL_MS = 3000;

const listVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

function formatSize(bytes: number | null): string {
  if (bytes === null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function RepoIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path
        d="M6 3.5h9l3 3V19a1.5 1.5 0 0 1-1.5 1.5h-10.5A1.5 1.5 0 0 1 4.5 19V5A1.5 1.5 0 0 1 6 3.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M9.5 9 8 10.5 9.5 12M14.5 9 16 10.5 14.5 12M12.5 8.5l-1 5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ScannerPage() {
  const [scans, setScans] = useState<ScanStatus[]>([]);
  const [scansLoaded, setScansLoaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Unlike /documents, `GET /scans` really exists — hydrate scan history
  // across sessions instead of only tracking what this tab uploaded.
  useEffect(() => {
    listScans()
      .then(setScans)
      .catch(() => {
        // A failed initial load just means an empty list — the upload
        // flow below still works standalone.
      })
      .finally(() => setScansLoaded(true));
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

        <UploadDropzone
          accept=".zip"
          uploading={uploading}
          idleLabel="Click or drag a .zip repository archive"
          uploadingLabel="Uploading and extracting…"
          hint="Scanned for security, GDPR, AI, and ISO 27001 evidence"
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

        {!scansLoaded ? (
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[72px]" />
            ))}
          </div>
        ) : scans.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-surface-border py-10 text-center">
            <RepoIcon className="h-8 w-8 text-muted opacity-60" />
            <p className="text-sm text-muted">No repositories scanned yet.</p>
          </div>
        ) : (
          <motion.ul
            className="flex flex-col gap-3"
            variants={listVariants}
            initial="hidden"
            animate="show"
          >
            <AnimatePresence initial={false}>
              {scans.map((scan) => (
                <motion.li
                  key={scan.id}
                  layout
                  variants={{
                    hidden: { opacity: 0, y: -8 },
                    show: { opacity: 1, y: 0 },
                  }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                >
                  <Link
                    href={`/scanner/${scan.id}`}
                    className="card-interactive block rounded-2xl border border-surface-border bg-surface p-4 hover:border-accent/40"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                        <RepoIcon className="h-4.5 w-4.5" />
                      </div>
                      <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                        {scan.original_filename}
                      </span>
                      <StatusBadge status={scan.status} />
                    </div>
                    {scan.status === "ready" && (
                      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-surface-border pt-3 text-xs text-muted">
                        <span>{scan.file_count} files</span>
                        <span>{formatSize(scan.total_size_bytes)}</span>
                        {scan.detected_languages.slice(0, 4).map((language) => (
                          <span
                            key={language}
                            className="rounded-full bg-accent-soft px-2 py-0.5 text-accent"
                          >
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
          </motion.ul>
        )}
      </div>
    </div>
  );
}

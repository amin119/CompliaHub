"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  getScan,
  getScanFiles,
  getScanFindings,
  type Finding,
  type RepositoryFile,
  type ScanStatus,
} from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import SeverityBadge from "@/components/SeverityBadge";

const TERMINAL_STATUSES = ["ready", "failed"];
const POLL_INTERVAL_MS = 3000;
const SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"];

const COMPONENT_TYPE_LABELS: Record<string, string> = {
  application_code: "Application code",
  test_code: "Test code",
  dependency_manifest: "Dependency manifest",
  infrastructure_as_code: "Infrastructure as code",
  ci_cd_config: "CI/CD config",
  database_migration: "Database migration",
  documentation: "Documentation",
  governance: "Governance",
  unknown: "Unclassified",
};

export default function ScanDetailPage() {
  const params = useParams<{ scanId: string }>();
  const scanId = params.scanId;

  const [scan, setScan] = useState<ScanStatus | null>(null);
  const [files, setFiles] = useState<RepositoryFile[]>([]);
  const [filterType, setFilterType] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [activeTab, setActiveTab] = useState<"files" | "findings">("files");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getScan(scanId)
      .then((result) => !cancelled && setScan(result))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Failed to load scan."));
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  // Poll until BOTH independent status tracks reach a terminal value — a
  // scan's files can be browsable (`status: "ready"`) well before the
  // heavier security-rule pass (`findings_status`) has finished.
  useEffect(() => {
    if (!scan) return;
    const scanDone = TERMINAL_STATUSES.includes(scan.status);
    const findingsDone = TERMINAL_STATUSES.includes(scan.findings_status);
    if (scanDone && findingsDone) return;

    const timeoutId = setTimeout(() => {
      getScan(scanId).then(setScan).catch(() => {});
    }, POLL_INTERVAL_MS);
    return () => clearTimeout(timeoutId);
  }, [scan, scanId]);

  useEffect(() => {
    if (!scan || scan.status !== "ready") return;
    getScanFiles(scanId, filterType ?? undefined)
      .then(setFiles)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load files."));
  }, [scan, scanId, filterType]);

  useEffect(() => {
    if (!scan || scan.findings_status !== "ready") return;
    getScanFindings(scanId)
      .then(setFindings)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load findings."));
  }, [scan, scanId]);

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center bg-background p-6">
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      </div>
    );
  }

  if (!scan) {
    return (
      <div className="flex flex-1 items-center justify-center bg-background p-6">
        <p className="text-sm text-muted">Loading…</p>
      </div>
    );
  }

  const componentTypesPresent = Array.from(new Set(files.map((f) => f.component_type)));
  const severityCounts = SEVERITY_ORDER.map((severity) => ({
    severity,
    count: findings.filter((f) => f.severity === severity).length,
  })).filter((entry) => entry.count > 0);

  return (
    <div className="flex flex-1 flex-col items-center bg-background">
      <div className="flex w-full max-w-3xl flex-1 flex-col px-4 py-6 sm:py-8">
        <header className="mb-6">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-2xl font-normal tracking-tight text-foreground">
              {scan.original_filename}
            </h1>
            <StatusBadge status={scan.status} />
            {scan.status === "ready" && scan.findings_status !== "ready" && (
              <StatusBadge status={scan.findings_status} />
            )}
          </div>
          {scan.status !== "ready" && scan.status !== "failed" && (
            <p className="mt-1 text-sm text-muted">
              Extracting and classifying files — this updates automatically.
            </p>
          )}
          {scan.status === "failed" && scan.error_message && (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">{scan.error_message}</p>
          )}
          {scan.findings_status === "failed" && scan.findings_error_message && (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">
              Security analysis failed: {scan.findings_error_message}
            </p>
          )}
        </header>

        {scan.status === "ready" && (
          <>
            <section className="mb-6 rounded-2xl border border-surface-border bg-surface p-4">
              <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm">
                <div>
                  <p className="text-xs text-muted">Files scanned</p>
                  <p className="font-medium text-foreground">{scan.file_count}</p>
                </div>
                <div>
                  <p className="text-xs text-muted">Languages</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {scan.detected_languages.length === 0 && (
                      <span className="text-muted">None detected</span>
                    )}
                    {scan.detected_languages.map((language) => (
                      <span key={language} className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs text-accent">
                        {language}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-muted">Frameworks</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {scan.detected_frameworks.length === 0 && (
                      <span className="text-muted">None detected</span>
                    )}
                    {scan.detected_frameworks.map((framework) => (
                      <span key={framework} className="rounded-full bg-surface-blue px-2.5 py-0.5 text-xs text-foreground">
                        {framework}
                      </span>
                    ))}
                  </div>
                </div>
                {scan.findings_status === "ready" && (
                  <div>
                    <p className="text-xs text-muted">Findings</p>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {severityCounts.length === 0 && (
                        <span className="text-muted">None found</span>
                      )}
                      {severityCounts.map(({ severity, count }) => (
                        <span key={severity} className="inline-flex items-center gap-1">
                          <SeverityBadge severity={severity} />
                          <span className="text-xs text-muted">×{count}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>

            <div className="mb-4 flex gap-1 border-b border-surface-border">
              <button
                type="button"
                onClick={() => setActiveTab("files")}
                className={`px-3 py-2 text-sm font-medium transition-colors ${
                  activeTab === "files"
                    ? "border-b-2 border-accent text-accent"
                    : "text-muted hover:text-foreground"
                }`}
              >
                Files
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("findings")}
                className={`px-3 py-2 text-sm font-medium transition-colors ${
                  activeTab === "findings"
                    ? "border-b-2 border-accent text-accent"
                    : "text-muted hover:text-foreground"
                }`}
              >
                Findings {findings.length > 0 && `(${findings.length})`}
              </button>
            </div>

            {activeTab === "files" && (
              <>
                <div className="mb-3 flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => setFilterType(null)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                      filterType === null
                        ? "border-accent bg-accent-soft text-accent"
                        : "border-surface-border text-muted hover:text-foreground"
                    }`}
                  >
                    All
                  </button>
                  {componentTypesPresent.map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setFilterType(type)}
                      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                        filterType === type
                          ? "border-accent bg-accent-soft text-accent"
                          : "border-surface-border text-muted hover:text-foreground"
                      }`}
                    >
                      {COMPONENT_TYPE_LABELS[type] ?? type}
                    </button>
                  ))}
                </div>

                <div className="overflow-hidden rounded-2xl border border-surface-border">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-surface text-xs text-muted">
                      <tr>
                        <th className="px-3 py-2 font-medium">Path</th>
                        <th className="px-3 py-2 font-medium">Language</th>
                        <th className="px-3 py-2 font-medium">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {files.map((file) => (
                        <tr key={file.id} className="border-t border-surface-border">
                          <td className="truncate px-3 py-2 font-mono text-xs text-foreground">
                            {file.relative_path}
                          </td>
                          <td className="px-3 py-2 text-xs text-muted">{file.language ?? "—"}</td>
                          <td className="px-3 py-2 text-xs text-muted">
                            {COMPONENT_TYPE_LABELS[file.component_type] ?? file.component_type}
                          </td>
                        </tr>
                      ))}
                      {files.length === 0 && (
                        <tr>
                          <td colSpan={3} className="px-3 py-4 text-center text-xs text-muted">
                            No files match this filter.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {activeTab === "findings" && (
              <div className="overflow-hidden rounded-2xl border border-surface-border">
                {scan.findings_status !== "ready" ? (
                  <p className="px-3 py-4 text-center text-xs text-muted">
                    Security analysis {scan.findings_status === "failed" ? "failed" : "still running"}…
                  </p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="bg-surface text-xs text-muted">
                      <tr>
                        <th className="px-3 py-2 font-medium">Severity</th>
                        <th className="px-3 py-2 font-medium">Title</th>
                        <th className="px-3 py-2 font-medium">Category</th>
                        <th className="px-3 py-2 font-medium">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {findings.map((finding) => (
                        <tr key={finding.id} className="border-t border-surface-border align-top">
                          <td className="px-3 py-2">
                            <SeverityBadge severity={finding.severity} />
                          </td>
                          <td className="px-3 py-2 text-xs text-foreground">
                            <p className="font-medium">{finding.title}</p>
                            <p className="mt-0.5 text-muted">{finding.summary}</p>
                          </td>
                          <td className="px-3 py-2 text-xs text-muted">{finding.category}</td>
                          <td className="px-3 py-2 text-xs text-muted">{finding.confidence}</td>
                        </tr>
                      ))}
                      {findings.length === 0 && (
                        <tr>
                          <td colSpan={4} className="px-3 py-4 text-center text-xs text-muted">
                            No findings — nothing this scan&apos;s rules flagged.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

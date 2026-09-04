"use client";

import { Fragment, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import {
  getScan,
  getScanFiles,
  getScanFinding,
  getScanFindings,
  validateFinding,
  ValidateFindingError,
  type Finding,
  type FindingDetail,
  type RepositoryFile,
  type ScanStatus,
} from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import SeverityBadge from "@/components/SeverityBadge";
import ComplianceDisclaimerBanner from "@/components/ComplianceDisclaimerBanner";
import PipelineProgress, { type PipelineStage } from "@/components/PipelineProgress";
import Skeleton from "@/components/Skeleton";

const TERMINAL_STATUSES = ["ready", "failed"];
const POLL_INTERVAL_MS = 3000;
const SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"];
const SEVERITY_BORDER: Record<string, string> = {
  CRITICAL: "border-l-red-500",
  HIGH: "border-l-orange-500",
  MEDIUM: "border-l-amber-500",
  LOW: "border-l-surface-border",
  INFORMATIONAL: "border-l-surface-border",
};

const FINDING_ASSESSMENT_LABELS: Record<string, string> = {
  likely_true_positive: "Likely true positive",
  likely_false_positive: "Likely false positive",
  insufficient_evidence: "Insufficient evidence",
};

const CONTEXT_RELATIONSHIP_LABELS: Record<string, string> = {
  supports_concern: "Supports concern",
  contradicts_concern: "Contradicts concern",
  not_addressed: "Not addressed",
};

function buildPipelineStages(scan: ScanStatus): PipelineStage[] {
  return [
    { key: "extract", label: "Extract", status: scan.status },
    { key: "security", label: "Security", status: scan.findings_status },
    { key: "gdpr", label: "GDPR", status: scan.privacy_status },
    { key: "ai", label: "AI / ISO 42001", status: scan.ai_status },
    { key: "iso27001", label: "ISO 27001", status: scan.iso27001_status },
  ];
}

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
  const [frameworkFilter, setFrameworkFilter] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"files" | "findings">("files");
  const [expandedFindingId, setExpandedFindingId] = useState<string | null>(null);
  const [findingDetails, setFindingDetails] = useState<Record<string, FindingDetail>>({});
  const [validatingFindingId, setValidatingFindingId] = useState<string | null>(null);
  const [validationNote, setValidationNote] = useState<
    Record<string, { message: string; kind: "info" | "error" }>
  >({});
  const [error, setError] = useState<string | null>(null);

  function toggleFinding(findingId: string) {
    setExpandedFindingId((current) => (current === findingId ? null : findingId));
    if (!findingDetails[findingId]) {
      getScanFinding(scanId, findingId)
        .then((detail) => setFindingDetails((prev) => ({ ...prev, [findingId]: detail })))
        .catch(() => {});
    }
  }

  async function handleValidate(findingId: string) {
    setValidatingFindingId(findingId);
    setValidationNote((prev) => {
      const next = { ...prev };
      delete next[findingId];
      return next;
    });
    try {
      const evidence = await validateFinding(scanId, findingId);
      setFindingDetails((prev) => {
        const detail = prev[findingId];
        if (!detail) return prev;
        return { ...prev, [findingId]: { ...detail, evidence: [evidence, ...detail.evidence] } };
      });
    } catch (err) {
      // 422 ("no standards ingested yet") is a normal fresh-install state,
      // styled as an informational note rather than an error; anything
      // else (404, 503 AI-unavailable) is a real error.
      const kind = err instanceof ValidateFindingError && err.status === 422 ? "info" : "error";
      const message = err instanceof Error ? err.message : "Validation failed.";
      setValidationNote((prev) => ({ ...prev, [findingId]: { message, kind } }));
    } finally {
      setValidatingFindingId(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    getScan(scanId)
      .then((result) => !cancelled && setScan(result))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Failed to load scan."));
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  // Poll until ALL independent status tracks reach a terminal value — a
  // scan's files can be browsable (`status: "ready"`) well before the
  // security-rule pass (`findings_status`), which itself finishes before
  // the GDPR pass (`privacy_status`), the AI/ISO 42001 pass (`ai_status`),
  // and the ISO 27001 mapping pass (`iso27001_status`), which runs last
  // since it maps the other three passes' findings onto controls.
  useEffect(() => {
    if (!scan) return;
    const scanDone = TERMINAL_STATUSES.includes(scan.status);
    const findingsDone = TERMINAL_STATUSES.includes(scan.findings_status);
    const privacyDone = TERMINAL_STATUSES.includes(scan.privacy_status);
    const aiDone = TERMINAL_STATUSES.includes(scan.ai_status);
    const iso27001Done = TERMINAL_STATUSES.includes(scan.iso27001_status);
    if (scanDone && findingsDone && privacyDone && aiDone && iso27001Done) return;

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

  // Re-fetch findings whenever any rule pass reaches "ready": the GDPR
  // (`privacy_status`), AI/ISO 42001 (`ai_status`), and ISO 27001
  // (`iso27001_status`) findings each land after the security
  // (`findings_status`) ones, and a single unfiltered fetch returns every
  // framework's rows.
  useEffect(() => {
    if (!scan) return;
    const anyReady = [
      scan.findings_status,
      scan.privacy_status,
      scan.ai_status,
      scan.iso27001_status,
    ].includes("ready");
    if (!anyReady) return;
    getScanFindings(scanId)
      .then(setFindings)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load findings."));
  }, [scan, scanId]);

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center bg-background p-6">
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center gap-2 text-center"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-500/15 dark:text-red-400">
            <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4">
              <path
                d="M8 5v3.5M8 11h.01"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
              <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" />
            </svg>
          </div>
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </motion.div>
      </div>
    );
  }

  if (!scan) {
    return (
      <div className="flex flex-1 flex-col items-center bg-background">
        <div className="flex w-full max-w-3xl flex-1 flex-col px-4 py-6 sm:py-8">
          <Skeleton className="mb-6 h-8 w-64" />
          <Skeleton className="mb-6 h-28" />
          <Skeleton className="mb-4 h-9 w-48" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  const componentTypesPresent = Array.from(new Set(files.map((f) => f.component_type)));
  // Framework filter chips, computed client-side from whichever framework
  // values are actually present — the same pattern the Files tab uses for
  // component types, so it scales to a third framework with no rework. A
  // null framework renders as "General".
  const frameworkLabel = (framework: string | null) => framework ?? "General";
  const frameworksPresent = Array.from(
    new Set(findings.map((f) => frameworkLabel(f.framework))),
  );
  const visibleFindings =
    frameworkFilter === null
      ? findings
      : findings.filter((f) => frameworkLabel(f.framework) === frameworkFilter);
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
            <StatusBadge
              status={
                [scan.status, scan.findings_status, scan.privacy_status, scan.ai_status, scan.iso27001_status].includes(
                  "failed",
                )
                  ? "failed"
                  : [scan.status, scan.findings_status, scan.privacy_status, scan.ai_status, scan.iso27001_status].every(
                        (s) => s === "ready",
                      )
                    ? "ready"
                    : "processing"
              }
            />
          </div>
          {scan.status === "failed" && scan.error_message && (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">{scan.error_message}</p>
          )}
          {scan.findings_status === "failed" && scan.findings_error_message && (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">
              Security analysis failed: {scan.findings_error_message}
            </p>
          )}
          {scan.privacy_status === "failed" && scan.privacy_error_message && (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">
              GDPR analysis failed: {scan.privacy_error_message}
            </p>
          )}
          {scan.ai_status === "failed" && scan.ai_error_message && (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">
              AI/ISO 42001 analysis failed: {scan.ai_error_message}
            </p>
          )}
          {scan.iso27001_status === "failed" && scan.iso27001_error_message && (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">
              ISO 27001 mapping failed: {scan.iso27001_error_message}
            </p>
          )}
        </header>

        <PipelineProgress stages={buildPipelineStages(scan)} />

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
              {(
                [
                  ["files", "Files"],
                  ["findings", `Findings${findings.length > 0 ? ` (${findings.length})` : ""}`],
                ] as const
              ).map(([tab, label]) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={`relative px-3 py-2 text-sm font-medium transition-colors ${
                    activeTab === tab ? "text-accent" : "text-muted hover:text-foreground"
                  }`}
                >
                  {label}
                  {activeTab === tab && (
                    <motion.span
                      layoutId="scan-tab-underline"
                      className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-accent"
                      transition={{ type: "spring", stiffness: 500, damping: 35 }}
                    />
                  )}
                </button>
              ))}
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

                <div className="themed-scroll overflow-x-auto rounded-2xl border border-surface-border">
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
                        <tr
                          key={file.id}
                          className="border-t border-surface-border transition-colors hover:bg-surface"
                        >
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
              <>
                {scan.findings_status === "ready" && frameworksPresent.length > 0 && (
                  <div className="mb-3 flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => setFrameworkFilter(null)}
                      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                        frameworkFilter === null
                          ? "border-accent bg-accent-soft text-accent"
                          : "border-surface-border text-muted hover:text-foreground"
                      }`}
                    >
                      All
                    </button>
                    {frameworksPresent.map((framework) => (
                      <button
                        key={framework}
                        type="button"
                        onClick={() => setFrameworkFilter(framework)}
                        className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                          frameworkFilter === framework
                            ? "border-accent bg-accent-soft text-accent"
                            : "border-surface-border text-muted hover:text-foreground"
                        }`}
                      >
                        {framework}
                      </button>
                    ))}
                  </div>
                )}

                {frameworkFilter === "ISO27001" && <ComplianceDisclaimerBanner />}

                <div className="themed-scroll overflow-x-auto rounded-2xl border border-surface-border">
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
                          <th className="px-3 py-2 font-medium">Framework</th>
                          <th className="px-3 py-2 font-medium">Category</th>
                          <th className="px-3 py-2 font-medium">Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleFindings.map((finding) => {
                          const expanded = expandedFindingId === finding.id;
                          const detail = findingDetails[finding.id];
                          return (
                            <Fragment key={finding.id}>
                              <tr
                                onClick={() => toggleFinding(finding.id)}
                                aria-expanded={expanded}
                                className={`cursor-pointer border-t border-l-2 border-surface-border align-top transition-colors hover:bg-surface ${
                                  SEVERITY_BORDER[finding.severity] ?? "border-l-surface-border"
                                } ${expanded ? "bg-surface" : ""}`}
                              >
                                <td className="px-3 py-2">
                                  <SeverityBadge severity={finding.severity} />
                                </td>
                                <td className="px-3 py-2 text-xs text-foreground">
                                  <div className="flex items-start gap-1.5">
                                    <motion.svg
                                      viewBox="0 0 16 16"
                                      fill="none"
                                      className="mt-0.5 h-3 w-3 shrink-0 text-muted"
                                      animate={{ rotate: expanded ? 90 : 0 }}
                                      transition={{ duration: 0.15 }}
                                    >
                                      <path
                                        d="M5 3.5 10.5 8 5 12.5"
                                        stroke="currentColor"
                                        strokeWidth="1.6"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                      />
                                    </motion.svg>
                                    <div>
                                      <p className="font-medium">{finding.title}</p>
                                      <p className="mt-0.5 text-muted">{finding.summary}</p>
                                    </div>
                                  </div>
                                </td>
                                <td className="px-3 py-2">
                                  <span className="rounded-full bg-surface-blue px-2.5 py-0.5 text-xs text-foreground">
                                    {finding.framework ?? "General"}
                                  </span>
                                </td>
                                <td className="px-3 py-2 text-xs text-muted">{finding.category}</td>
                                <td className="px-3 py-2 text-xs text-muted">{finding.confidence}</td>
                              </tr>
                              <tr>
                                <td colSpan={5} className="p-0">
                                  <AnimatePresence initial={false}>
                                    {expanded && (
                                      <motion.div
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: "auto", opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        transition={{ duration: 0.2, ease: "easeOut" }}
                                        className="overflow-hidden"
                                      >
                                        <div className="border-t border-surface-border bg-background px-4 py-3 text-xs">
                                          {!detail ? (
                                            <p className="text-muted">Loading detail…</p>
                                          ) : (
                                            <div className="flex flex-col gap-3">
                                              <div className="flex flex-wrap items-center gap-2">
                                                <button
                                                  type="button"
                                                  onClick={(event) => {
                                                    event.stopPropagation();
                                                    void handleValidate(finding.id);
                                                  }}
                                                  disabled={validatingFindingId === finding.id}
                                                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                                                    detail.evidence.some(
                                                      (e) => e.source_type === "llm_reasoning",
                                                    )
                                                      ? "border border-surface-border text-muted hover:text-accent"
                                                      : "bg-cta text-accent-foreground hover:opacity-90"
                                                  }`}
                                                >
                                                  {validatingFindingId === finding.id ? (
                                                    <>
                                                      <motion.span
                                                        className="h-2.5 w-2.5 rounded-full border-[1.5px] border-current border-t-transparent"
                                                        animate={{ rotate: 360 }}
                                                        transition={{
                                                          duration: 0.7,
                                                          repeat: Infinity,
                                                          ease: "linear",
                                                        }}
                                                      />
                                                      Validating…
                                                    </>
                                                  ) : detail.evidence.some(
                                                      (e) => e.source_type === "llm_reasoning",
                                                    ) ? (
                                                    "Re-validate with AI"
                                                  ) : (
                                                    "Validate with AI"
                                                  )}
                                                </button>
                                              </div>
                                              {validationNote[finding.id] && (
                                                <p
                                                  className={
                                                    validationNote[finding.id].kind === "info"
                                                      ? "text-muted"
                                                      : "text-red-600 dark:text-red-400"
                                                  }
                                                >
                                                  {validationNote[finding.id].message}
                                                </p>
                                              )}
                                              <div>
                                                <p className="mb-1 font-medium text-muted">Reasoning</p>
                                                <p className="text-foreground">{detail.reasoning}</p>
                                              </div>
                                              {detail.recommendation && (
                                                <div>
                                                  <p className="mb-1 font-medium text-muted">
                                                    Recommendation
                                                  </p>
                                                  <p className="text-foreground">
                                                    {detail.recommendation}
                                                  </p>
                                                </div>
                                              )}
                                              {detail.evidence.length > 0 && (
                                                <div>
                                                  <p className="mb-1.5 font-medium text-muted">
                                                    Evidence ({detail.evidence.length})
                                                  </p>
                                                  <div className="flex flex-col gap-2">
                                                    {detail.evidence.map((evidence) => {
                                                      const isAiReview =
                                                        evidence.source_type === "llm_reasoning";
                                                      const metadata = evidence.evidence_metadata as
                                                        | {
                                                            finding_assessment?: string;
                                                            context_relationship?: string;
                                                            retrieved_citations?: {
                                                              clause_number: string | null;
                                                              document_filename: string;
                                                            }[];
                                                          }
                                                        | null;
                                                      return (
                                                        <div
                                                          key={evidence.id}
                                                          className={`rounded-xl border p-2.5 ${
                                                            isAiReview
                                                              ? "border-purple/30 bg-purple/5"
                                                              : "border-surface-border bg-surface"
                                                          }`}
                                                        >
                                                          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-muted">
                                                            {evidence.file_path && (
                                                              <span className="text-foreground">
                                                                {evidence.file_path}
                                                                {evidence.line_start &&
                                                                  `:${evidence.line_start}${
                                                                    evidence.line_end &&
                                                                    evidence.line_end !==
                                                                      evidence.line_start
                                                                      ? `-${evidence.line_end}`
                                                                      : ""
                                                                  }`}
                                                              </span>
                                                            )}
                                                            {evidence.source_type && (
                                                              <span
                                                                className={`rounded-full px-1.5 py-0 ${
                                                                  isAiReview
                                                                    ? "bg-purple/15 text-purple"
                                                                    : "bg-accent-soft text-accent"
                                                                }`}
                                                              >
                                                                {isAiReview
                                                                  ? "AI review"
                                                                  : evidence.source_type}
                                                              </span>
                                                            )}
                                                          </div>
                                                          {isAiReview && metadata && (
                                                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                                                              {metadata.finding_assessment && (
                                                                <span className="rounded-full bg-surface px-2 py-0.5 text-[11px] font-medium text-foreground">
                                                                  {FINDING_ASSESSMENT_LABELS[
                                                                    metadata.finding_assessment
                                                                  ] ?? metadata.finding_assessment}
                                                                </span>
                                                              )}
                                                              {metadata.context_relationship && (
                                                                <span className="rounded-full bg-surface px-2 py-0.5 text-[11px] font-medium text-foreground">
                                                                  {CONTEXT_RELATIONSHIP_LABELS[
                                                                    metadata.context_relationship
                                                                  ] ?? metadata.context_relationship}
                                                                </span>
                                                              )}
                                                            </div>
                                                          )}
                                                          {evidence.snippet && (
                                                            <pre className="themed-scroll mt-1.5 overflow-x-auto rounded-lg bg-background p-2 font-mono text-[11px] text-foreground">
                                                              {evidence.snippet}
                                                            </pre>
                                                          )}
                                                          {!evidence.snippet && evidence.description && (
                                                            <p className="mt-1 text-foreground">
                                                              {evidence.description}
                                                            </p>
                                                          )}
                                                          {isAiReview &&
                                                            metadata?.retrieved_citations &&
                                                            metadata.retrieved_citations.length > 0 && (
                                                              <div className="mt-1.5 text-[11px] text-muted">
                                                                Grounded in:{" "}
                                                                {metadata.retrieved_citations
                                                                  .map(
                                                                    (c) =>
                                                                      `${c.clause_number ?? "—"} (${c.document_filename})`,
                                                                  )
                                                                  .join(", ")}
                                                              </div>
                                                            )}
                                                        </div>
                                                      );
                                                    })}
                                                  </div>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      </motion.div>
                                    )}
                                  </AnimatePresence>
                                </td>
                              </tr>
                            </Fragment>
                          );
                        })}
                        {visibleFindings.length === 0 && (
                          <tr>
                            <td colSpan={5} className="px-3 py-4 text-center text-xs text-muted">
                              No findings — nothing this scan&apos;s rules flagged.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

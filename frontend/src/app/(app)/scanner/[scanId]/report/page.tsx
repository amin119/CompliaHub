"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  getScanFinding,
  getScanFindings,
  getScanSummary,
  type Finding,
  type FindingDetail,
  type ScanSummary,
} from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";
import FindingStatusBadge from "@/components/FindingStatusBadge";
import ComplianceDisclaimerBanner from "@/components/ComplianceDisclaimerBanner";
import ReportDisclaimerBanner from "@/components/ReportDisclaimerBanner";
import Skeleton from "@/components/Skeleton";
import StatGrid from "@/components/StatGrid";
import BarRow from "@/components/BarRow";
import { buttonClasses, CHIP_BASE } from "@/lib/ui";

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

// Mirrors SeverityBadge's own red -> orange -> amber -> neutral scale, so
// the bar color and the badge color next to it always agree.
const SEVERITY_BAR_FILL: Record<string, string> = {
  CRITICAL: "bg-red-500",
  HIGH: "bg-orange-500",
  MEDIUM: "bg-amber-500",
  LOW: "bg-muted",
  INFORMATIONAL: "bg-muted",
};

// Same left-border-by-severity treatment the scan detail table uses, so a
// page of findings reads at a glance in both places.
const SEVERITY_BORDER: Record<string, string> = {
  CRITICAL: "border-l-red-500",
  HIGH: "border-l-orange-500",
  MEDIUM: "border-l-amber-500",
  LOW: "border-l-surface-border",
  INFORMATIONAL: "border-l-surface-border",
};

/**
 * Temporarily forces the whole app into light mode for the print output —
 * not a CSS/`@custom-variant` trick. The dark-mode variant
 * (`globals.css`'s `@custom-variant dark`) is keyed off the `data-theme`
 * DOM attribute, not a media query, and every literal `dark:` utility
 * class (e.g. SeverityBadge's `dark:bg-red-500/15`) stays active whenever
 * that attribute is "dark" — a `@media print` CSS override alone can't
 * reach those. Flipping the attribute itself, then restoring it once the
 * print dialog closes (`afterprint`, a standard DOM event), fixes every
 * component with zero per-component changes.
 */
function handlePrint() {
  const root = document.documentElement;
  const previousTheme = root.dataset.theme;
  root.dataset.theme = "light";
  const restore = () => {
    if (previousTheme) root.dataset.theme = previousTheme;
    else delete root.dataset.theme;
    window.removeEventListener("afterprint", restore);
  };
  window.addEventListener("afterprint", restore);
  window.print();
}

export default function ScanReportPage() {
  const params = useParams<{ scanId: string }>();
  const scanId = params.scanId;

  const [summary, setSummary] = useState<ScanSummary | null>(null);
  const [findingDetails, setFindingDetails] = useState<FindingDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getScanSummary(scanId)
      .then((result) => !cancelled && setSummary(result))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Failed to load report."));
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  useEffect(() => {
    let cancelled = false;
    getScanFindings(scanId)
      .then((findings: Finding[]) =>
        Promise.all(findings.map((f) => getScanFinding(scanId, f.id))),
      )
      .then((details) => !cancelled && setFindingDetails(details))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Failed to load findings."));
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center bg-background p-6">
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      </div>
    );
  }

  if (!summary || !findingDetails) {
    return (
      <div className="flex flex-1 flex-col items-center bg-background">
        <div className="flex w-full max-w-3xl flex-1 flex-col px-4 py-6 sm:py-8">
          <Skeleton className="mb-6 h-8 w-64" />
          <Skeleton className="mb-6 h-28" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  const hasIso27001Findings = summary.framework_counts.some(
    (f) => f.framework === "ISO27001" && f.count > 0,
  );
  const incompleteTracks = [
    ["status", "Extraction"],
    ["findings_status", "Security analysis"],
    ["privacy_status", "GDPR analysis"],
    ["ai_status", "AI / ISO 42001 analysis"],
    ["iso27001_status", "ISO 27001 mapping"],
  ].filter(([key]) => summary[key as keyof ScanSummary] !== "ready");

  return (
    <div className="flex flex-1 flex-col items-center bg-background">
      <div className="flex w-full max-w-3xl flex-1 flex-col px-4 py-6 sm:py-8 print:max-w-none print:px-0">
        <div className="mb-4 flex items-center justify-between print:hidden">
          <Link
            href={`/scanner/${scanId}`}
            className="text-sm font-medium text-accent hover:opacity-70"
          >
            ← Back to scan
          </Link>
          <button
            type="button"
            onClick={handlePrint}
            className={buttonClasses({ size: "sm" })}
          >
            Print / Save as PDF
          </button>
        </div>

        <header className="mb-5 flex items-start gap-3.5">
          <span
            aria-hidden="true"
            className="mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent print:hidden"
          >
            <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
              <path
                d="M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5A1.5 1.5 0 0 1 7 3.5Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
              <path d="M9 13h6M9 16h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </span>
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
              {summary.original_filename}
            </h1>
            <p className="mt-1 text-sm text-muted">
              Compliance evidence report, generated{" "}
              {new Date(summary.generated_at).toLocaleString()}
            </p>
          </div>
        </header>

        <ReportDisclaimerBanner />

        {incompleteTracks.length > 0 && (
          <div className="mb-4 rounded-xl border border-red-300/60 bg-red-50 px-3 py-2.5 text-xs text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
            The following analysis stages had not finished at the time this report was generated,
            so their sections below may be incomplete:{" "}
            {incompleteTracks.map(([, label]) => label).join(", ")}.
          </div>
        )}

        <StatGrid
          stats={[
            { label: "Files scanned", value: summary.file_count },
            {
              label: "Languages",
              value: summary.detected_languages.length,
              content:
                summary.detected_languages.length === 0 ? (
                  <span className="text-xs text-muted">None detected</span>
                ) : (
                  summary.detected_languages.map((language) => (
                    <span key={language} className={CHIP_BASE}>
                      {language}
                    </span>
                  ))
                ),
            },
            {
              label: "Frameworks",
              value: summary.detected_frameworks.length,
              content:
                summary.detected_frameworks.length === 0 ? (
                  <span className="text-xs text-muted">None detected</span>
                ) : (
                  summary.detected_frameworks.map((framework) => (
                    <span key={framework} className={CHIP_BASE}>
                      {framework}
                    </span>
                  ))
                ),
            },
            { label: "Total findings", value: findingDetails.length },
          ]}
        />

        <section className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-surface-border bg-surface-raised p-4">
            <p className="mb-3 text-xs font-medium text-muted">Findings by severity</p>
            <div className="flex flex-col">
              {summary.severity_counts.map(({ severity, count }) => (
                <BarRow
                  key={severity}
                  label={severity}
                  count={count}
                  max={Math.max(1, ...summary.severity_counts.map((s) => s.count))}
                  barClassName={SEVERITY_BAR_FILL[severity] ?? "bg-muted"}
                  labelSlot={<SeverityBadge severity={severity} />}
                />
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-surface-border bg-surface-raised p-4">
            <p className="mb-3 text-xs font-medium text-muted">Findings by framework</p>
            <div className="flex flex-col">
              {summary.framework_counts.map(({ framework, count }) => (
                <BarRow
                  key={framework ?? "general"}
                  label={framework ?? "General"}
                  count={count}
                  max={Math.max(1, ...summary.framework_counts.map((f) => f.count))}
                  barClassName="bg-accent"
                />
              ))}
            </div>
          </div>
        </section>

        <section className="mb-6 rounded-2xl border border-surface-border bg-surface-raised p-4">
          <p className="mb-3 text-xs font-medium text-muted">Findings by status</p>
          <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
            {summary.status_counts.map(({ status, count }) => (
              <BarRow
                key={status}
                label={status}
                count={count}
                max={Math.max(1, ...summary.status_counts.map((s) => s.count))}
                barClassName="bg-accent"
                labelSlot={<FindingStatusBadge status={status} />}
                labelWidthClassName="w-44"
              />
            ))}
          </div>
        </section>

        <p className="mb-3 text-xs font-medium text-muted">Human review coverage</p>
        <StatGrid
          stats={[
            { label: "Total findings", value: summary.review_coverage.total_findings },
            { label: "Reviewed", value: summary.review_coverage.reviewed_findings },
            { label: "Review actions recorded", value: summary.review_coverage.total_reviews },
            {
              label: "Flagged, not yet reviewed",
              content: (
                <span className="text-lg font-semibold text-amber-700 dark:text-amber-400">
                  {summary.review_coverage.requires_human_review_unreviewed_count}
                </span>
              ),
            },
          ]}
        />

        {hasIso27001Findings && <ComplianceDisclaimerBanner />}

        <section>
          <h2 className="font-display mb-3 text-lg font-semibold text-foreground">
            All findings <span className="text-muted">({findingDetails.length})</span>
          </h2>
          <div className="flex flex-col gap-3">
            {findingDetails.map((finding) => (
              <div
                key={finding.id}
                className={`break-inside-avoid-page rounded-2xl border border-l-4 border-surface-border bg-surface-raised p-4 text-xs ${
                  SEVERITY_BORDER[finding.severity] ?? "border-l-surface-border"
                }`}
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <SeverityBadge severity={finding.severity} />
                  <FindingStatusBadge status={finding.status} />
                  <span className="rounded-full border border-surface-border px-2.5 py-0.5 text-foreground">
                    {finding.framework ?? "General"}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium text-foreground">{finding.title}</p>
                <p className="mt-0.5 text-muted">
                  {finding.category} · {finding.rule_id} · confidence: {finding.confidence}
                </p>
                <p className="mt-2 text-foreground">{finding.summary}</p>

                <div className="mt-2">
                  <p className="mb-1 font-medium text-muted">Reasoning</p>
                  <p className="text-foreground">{finding.reasoning}</p>
                </div>
                {finding.recommendation && (
                  <div className="mt-2">
                    <p className="mb-1 font-medium text-muted">Recommendation</p>
                    <p className="text-foreground">{finding.recommendation}</p>
                  </div>
                )}

                {finding.evidence.length > 0 && (
                  <div className="mt-2">
                    <p className="mb-1.5 font-medium text-muted">
                      Evidence ({finding.evidence.length})
                    </p>
                    <div className="flex flex-col gap-1.5">
                      {finding.evidence.map((evidence) => {
                        const isAiReview = evidence.source_type === "llm_reasoning";
                        const metadata = evidence.evidence_metadata as
                          | { finding_assessment?: string; context_relationship?: string }
                          | null;
                        return (
                          <div
                            key={evidence.id}
                            className={`rounded-lg border p-2 ${
                              isAiReview
                                ? "border-ai/30 bg-ai/5"
                                : "border-surface-border bg-background"
                            }`}
                          >
                            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-muted">
                              {evidence.file_path && (
                                <span className="text-foreground">
                                  {evidence.file_path}
                                  {evidence.line_start && `:${evidence.line_start}`}
                                </span>
                              )}
                              {evidence.source_type && (
                                <span
                                  className={`rounded-full px-1.5 py-0 ${
                                    isAiReview
                                      ? "bg-ai/15 text-ai"
                                      : "bg-accent-soft text-accent"
                                  }`}
                                >
                                  {isAiReview ? "AI review" : evidence.source_type}
                                </span>
                              )}
                              {isAiReview && metadata?.finding_assessment && (
                                <span className="rounded-full bg-background px-1.5 py-0 text-foreground">
                                  {FINDING_ASSESSMENT_LABELS[metadata.finding_assessment] ??
                                    metadata.finding_assessment}
                                </span>
                              )}
                              {isAiReview && metadata?.context_relationship && (
                                <span className="rounded-full bg-background px-1.5 py-0 text-foreground">
                                  {CONTEXT_RELATIONSHIP_LABELS[metadata.context_relationship] ??
                                    metadata.context_relationship}
                                </span>
                              )}
                            </div>
                            {evidence.snippet ? (
                              <pre className="mt-1 overflow-x-auto rounded bg-surface p-1.5 font-mono text-[11px] text-foreground">
                                {evidence.snippet}
                              </pre>
                            ) : (
                              evidence.description && (
                                <p className="mt-1 text-foreground">{evidence.description}</p>
                              )
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {finding.reviews.length > 0 && (
                  <div className="mt-2">
                    <p className="mb-1.5 font-medium text-muted">
                      Review history ({finding.reviews.length})
                    </p>
                    <div className="flex flex-col gap-1.5">
                      {finding.reviews.map((review) => (
                        <div
                          key={review.id}
                          className="rounded-lg border border-surface-border bg-background p-2"
                        >
                          <div className="flex flex-wrap items-center gap-1.5">
                            {review.previous_status && (
                              <>
                                <FindingStatusBadge status={review.previous_status} />
                                <span className="text-muted">→</span>
                              </>
                            )}
                            <FindingStatusBadge status={review.decision} />
                            <span className="text-[11px] text-muted">
                              {review.reviewer_name ?? "Anonymous reviewer"} ·{" "}
                              {new Date(review.created_at).toLocaleString()}
                            </span>
                          </div>
                          <p className="mt-1 text-foreground">{review.notes}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {findingDetails.length === 0 && (
              <p className="text-center text-muted">
                No findings — nothing this scan&apos;s rules flagged.
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

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
            className="rounded-full bg-cta px-4 py-1.5 text-sm font-medium text-accent-foreground transition-opacity hover:opacity-90"
          >
            Print / Save as PDF
          </button>
        </div>

        <header className="mb-4">
          <h1 className="font-display text-2xl font-normal tracking-tight text-foreground">
            {summary.original_filename}
          </h1>
          <p className="mt-1 text-sm text-muted">
            Compliance evidence report — generated {new Date(summary.generated_at).toLocaleString()}
          </p>
        </header>

        <ReportDisclaimerBanner />

        {incompleteTracks.length > 0 && (
          <div className="mb-4 rounded-xl border border-red-300/60 bg-red-50 px-3 py-2.5 text-xs text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
            The following analysis stages had not finished at the time this report was generated,
            so their sections below may be incomplete:{" "}
            {incompleteTracks.map(([, label]) => label).join(", ")}.
          </div>
        )}

        <section className="mb-6 rounded-2xl border border-surface-border bg-surface p-4">
          <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm">
            <div>
              <p className="text-xs text-muted">Files scanned</p>
              <p className="font-medium text-foreground">{summary.file_count}</p>
            </div>
            <div>
              <p className="text-xs text-muted">Languages</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {summary.detected_languages.length === 0 ? (
                  <span className="text-muted">None detected</span>
                ) : (
                  summary.detected_languages.map((language) => (
                    <span
                      key={language}
                      className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs text-accent"
                    >
                      {language}
                    </span>
                  ))
                )}
              </div>
            </div>
            <div>
              <p className="text-xs text-muted">Frameworks</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {summary.detected_frameworks.length === 0 ? (
                  <span className="text-muted">None detected</span>
                ) : (
                  summary.detected_frameworks.map((framework) => (
                    <span
                      key={framework}
                      className="rounded-full bg-surface-blue px-2.5 py-0.5 text-xs text-foreground"
                    >
                      {framework}
                    </span>
                  ))
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-surface-border bg-surface p-4">
            <p className="mb-2 text-xs font-medium text-muted">Findings by severity</p>
            <table className="w-full text-left text-sm">
              <tbody>
                {summary.severity_counts.map(({ severity, count }) => (
                  <tr key={severity} className="border-t border-surface-border first:border-0">
                    <td className="py-1.5 pr-2">
                      <SeverityBadge severity={severity} />
                    </td>
                    <td className="py-1.5 text-right font-medium text-foreground">{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="rounded-2xl border border-surface-border bg-surface p-4">
            <p className="mb-2 text-xs font-medium text-muted">Findings by status</p>
            <table className="w-full text-left text-sm">
              <tbody>
                {summary.status_counts.map(({ status, count }) => (
                  <tr key={status} className="border-t border-surface-border first:border-0">
                    <td className="py-1.5 pr-2">
                      <FindingStatusBadge status={status} />
                    </td>
                    <td className="py-1.5 text-right font-medium text-foreground">{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="rounded-2xl border border-surface-border bg-surface p-4">
            <p className="mb-2 text-xs font-medium text-muted">Findings by framework</p>
            <table className="w-full text-left text-sm">
              <tbody>
                {summary.framework_counts.map(({ framework, count }) => (
                  <tr
                    key={framework ?? "general"}
                    className="border-t border-surface-border first:border-0"
                  >
                    <td className="py-1.5 pr-2">
                      <span className="rounded-full bg-surface-blue px-2.5 py-0.5 text-xs text-foreground">
                        {framework ?? "General"}
                      </span>
                    </td>
                    <td className="py-1.5 text-right font-medium text-foreground">{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mb-6 rounded-2xl border border-surface-border bg-surface p-4">
          <p className="mb-3 text-xs font-medium text-muted">Human review coverage</p>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-xs text-muted">Total findings</p>
              <p className="text-lg font-medium text-foreground">
                {summary.review_coverage.total_findings}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">Reviewed</p>
              <p className="text-lg font-medium text-foreground">
                {summary.review_coverage.reviewed_findings}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">Review actions recorded</p>
              <p className="text-lg font-medium text-foreground">
                {summary.review_coverage.total_reviews}
              </p>
            </div>
            <div className="rounded-xl bg-amber-50 px-3 py-2 dark:bg-amber-950/40">
              <p className="text-xs text-amber-800 dark:text-amber-300">
                Flagged, not yet reviewed
              </p>
              <p className="text-lg font-medium text-amber-900 dark:text-amber-200">
                {summary.review_coverage.requires_human_review_unreviewed_count}
              </p>
            </div>
          </div>
        </section>

        {hasIso27001Findings && <ComplianceDisclaimerBanner />}

        <section>
          <p className="mb-3 text-xs font-medium text-muted">
            All findings ({findingDetails.length})
          </p>
          <div className="flex flex-col gap-3">
            {findingDetails.map((finding) => (
              <div
                key={finding.id}
                className="break-inside-avoid-page rounded-2xl border border-surface-border bg-surface p-4 text-xs"
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <SeverityBadge severity={finding.severity} />
                  <FindingStatusBadge status={finding.status} />
                  <span className="rounded-full bg-surface-blue px-2.5 py-0.5 text-foreground">
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
                                ? "border-purple/30 bg-purple/5"
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
                                      ? "bg-purple/15 text-purple"
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

/**
 * Phase 8: always rendered on every report, unconditionally — unlike
 * `ComplianceDisclaimerBanner` (ISO27001-Annex-A-specific, shown only when
 * filtered to that framework), this is the project-wide anti-overclaiming
 * disclaimer every report needs regardless of which frameworks it covers.
 * Restates this project's standing "technical evidence coverage, not
 * certification" principle (see docs/scanner-phase-5-iso27001-mapping.md)
 * directly on the one artifact most likely to be shown to someone else.
 */
export default function ReportDisclaimerBanner() {
  return (
    <div className="mb-4 rounded-xl border border-amber-300/60 bg-amber-50 px-3 py-2.5 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200">
      This report presents technical evidence coverage collected by automated scanning and any
      recorded human review — it is not a certification, audit opinion, or compliance score, and
      must not be represented as one. Every count below reflects findings and reviews recorded in
      this system only.
    </div>
  );
}

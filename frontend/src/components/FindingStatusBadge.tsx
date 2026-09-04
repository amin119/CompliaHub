const STATUS_LABELS: Record<string, string> = {
  VERIFIED: "Verified",
  PARTIALLY_VERIFIED: "Partially verified",
  NOT_VERIFIED: "Not verified",
  POTENTIAL_NON_COMPLIANCE: "Potential non-compliance",
  NOT_APPLICABLE: "Not applicable",
  REQUIRES_HUMAN_REVIEW: "Requires human review",
};

const STATUS_STYLES: Record<string, string> = {
  VERIFIED: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400",
  PARTIALLY_VERIFIED: "bg-teal-100 text-teal-700 dark:bg-teal-500/15 dark:text-teal-400",
  NOT_VERIFIED: "bg-surface text-muted",
  POTENTIAL_NON_COMPLIANCE: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400",
  NOT_APPLICABLE: "bg-surface text-muted",
  REQUIRES_HUMAN_REVIEW: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400",
};

export const FINDING_STATUSES = [
  "VERIFIED",
  "PARTIALLY_VERIFIED",
  "NOT_VERIFIED",
  "POTENTIAL_NON_COMPLIANCE",
  "NOT_APPLICABLE",
  "REQUIRES_HUMAN_REVIEW",
] as const;

export function findingStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

/**
 * A badge for `Finding.status`'s 6-value spec vocabulary — a different axis
 * from `StatusBadge`'s scan/document pending/ready/failed lifecycle, and
 * from `SeverityBadge`'s severity scale. Phase 7 is the first place any of
 * these 6 values get a dedicated visual treatment in the UI at all.
 */
export default function FindingStatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-surface text-muted";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}>
      {findingStatusLabel(status)}
    </span>
  );
}

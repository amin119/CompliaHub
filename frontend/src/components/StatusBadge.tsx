const TERMINAL_STATUSES = ["ready", "failed"];

function statusStyle(status: string): { dot: string; text: string } {
  if (status === "ready") return { dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" };
  if (status === "failed") return { dot: "bg-red-500", text: "text-red-600 dark:text-red-400" };
  return { dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400" };
}

/**
 * Shared by `/documents` and `/scanner` — both poll an entity through the
 * same pending/in-progress/ready/failed shape, so the pending-state pulse
 * indicator and color mapping only need to exist once.
 */
export default function StatusBadge({ status }: { status: string }) {
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

import type { ReactNode } from "react";

/**
 * The shared header for every app-shell page (`/chat`, `/documents`,
 * `/scanner`, `/scanner/[scanId]`). Before this existed, each page hand-rolled
 * its own `<h1>` + description block with no consistent rhythm or visual
 * anchor — a page in the "quiet register" still deserves a real header, not
 * a plain heading, and one shared component means all four get it at once
 * and stay in sync by construction.
 *
 * The icon badge borrows the landing page's own vocabulary (a colored-soft
 * circle, same shape `SectionDemo`'s empty states and `Logo` badges use)
 * rather than inventing new chrome — the app and the landing page are one
 * product, not two.
 */
export default function PageHeader({
  icon,
  title,
  description,
  tone = "accent",
  actions,
}: {
  icon: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  tone?: "accent" | "mark";
  actions?: ReactNode;
}) {
  const badgeClass =
    tone === "mark" ? "bg-mark-soft text-mark-contrast" : "bg-accent-soft text-accent";

  return (
    <header className="mb-7 flex items-start justify-between gap-4">
      <div className="flex items-start gap-3.5">
        <span
          aria-hidden="true"
          className={`mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${badgeClass}`}
        >
          {icon}
        </span>
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {description && <p className="mt-1 max-w-md text-sm text-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="mt-1.5 flex shrink-0 items-center gap-3">{actions}</div>}
    </header>
  );
}

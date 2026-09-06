import clsx from "clsx";

/**
 * The shared button and badge vocabulary. Deliberately class builders rather
 * than wrapper components: this codebase uses `<Link>` for navigation and
 * `<button>` for actions, and a single wrapper that has to forward both sets
 * of props ends up worse than a string. Anything that needs magnetism wraps
 * these with `MagneticLink`.
 */

export type ButtonVariant = "primary" | "secondary" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-full font-medium " +
  "transition-[background-color,border-color,color,opacity,box-shadow] " +
  "duration-[var(--dur-fast)] ease-[var(--ease-out-quart)] " +
  "disabled:cursor-not-allowed disabled:opacity-50";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-cta text-accent-contrast shadow-[0_10px_30px_-16px_var(--accent)] hover:opacity-90",
  secondary:
    "border border-surface-border bg-surface-raised text-foreground hover:border-accent hover:text-accent",
  ghost: "text-muted hover:text-accent",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "px-3.5 py-2 text-xs",
  md: "px-5 py-2.5 text-sm",
  lg: "px-7 py-3.5 text-sm",
};

export function buttonClasses(
  options: { variant?: ButtonVariant; size?: ButtonSize; className?: string } = {},
) {
  const { variant = "primary", size = "md", className } = options;
  return clsx(BUTTON_BASE, BUTTON_VARIANTS[variant], BUTTON_SIZES[size], className);
}

/**
 * One shape/size for every badge in the product — severity, scan status, and
 * finding status all share this and supply only their own colors, so a row of
 * mixed badges reads as one system instead of three.
 */
export const BADGE_BASE =
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap";

/** A tinted "chip" for metadata (languages, frameworks, file types). */
export const CHIP_BASE =
  "inline-flex items-center rounded-full bg-surface px-2.5 py-0.5 text-xs text-muted";

/**
 * A toggleable filter pill — the scanner's file-type, framework and
 * needs-review filters. Unlike `CHIP_BASE` these are interactive, which is
 * why the selected state is allowed to use the accent: on this page accent
 * consistently means "you did this / you can click this".
 */
export function filterPillClasses(active: boolean) {
  return clsx(
    "rounded-full border px-3 py-1 text-xs font-medium transition-colors duration-[var(--dur-fast)]",
    active
      ? "border-accent bg-accent-soft text-accent"
      : "border-surface-border text-muted hover:text-foreground",
  );
}

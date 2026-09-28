"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useMagnetic } from "@/hooks/useMagnetic";

/**
 * A link that leans toward the pointer. Landing-page CTAs only — the app's
 * quiet register uses plain links (see DESIGN-SYSTEM.md's two-register
 * principle). Degrades to an ordinary link on touch and under
 * `prefers-reduced-motion`, since `useMagnetic` no-ops there.
 */
export default function MagneticLink({
  href,
  children,
  className,
  cursorLabel,
  strength,
}: {
  href: string;
  children: ReactNode;
  className?: string;
  /** Label shown inside the custom cursor while hovering this link. */
  cursorLabel?: string;
  strength?: number;
}) {
  const ref = useMagnetic<HTMLAnchorElement>(strength);

  return (
    <Link ref={ref} href={href} className={className} data-cursor={cursorLabel}>
      {children}
    </Link>
  );
}

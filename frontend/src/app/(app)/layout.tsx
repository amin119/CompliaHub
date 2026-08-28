"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Logo from "@/components/Logo";

const NAV_LINKS = [
  { href: "/chat", label: "Chat" },
  { href: "/documents", label: "Documents" },
];

/**
 * Shared shell for the product itself (chat + documents) — the marketing
 * landing page at "/" deliberately does NOT use this layout (a Next.js
 * route group, `(app)`, so these URLs stay `/chat` and `/documents`
 * without an `/app` prefix while still sharing this nav+chrome).
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <nav className="sticky top-0 z-20 flex items-center gap-6 border-b border-surface-border/80 bg-background/80 px-4 py-3 backdrop-blur-md sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-foreground">
          <Logo className="h-6 w-6 text-accent" />
          <span className="text-sm font-semibold tracking-tight">ComplianceHub</span>
        </Link>
        <div className="flex items-center gap-1">
          {NAV_LINKS.map((link) => {
            const active = pathname?.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`relative rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "text-accent"
                    : "text-zinc-500 hover:text-foreground dark:text-zinc-400"
                }`}
              >
                {active && (
                  <span className="absolute inset-0 -z-10 rounded-full bg-accent-soft" />
                )}
                {link.label}
              </Link>
            );
          })}
        </div>
      </nav>
      <div className="flex flex-1 flex-col">{children}</div>
    </div>
  );
}

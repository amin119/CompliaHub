import Link from "next/link";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";

const NAV_LINKS = [
  { href: "#showcase", label: "Showcase" },
  { href: "#features", label: "Features" },
  { href: "#use-cases", label: "Use cases" },
];

/**
 * Structure follows the reference design (home page design/home page.svg)
 * exactly: logo left, center nav links, a single pill CTA right. The
 * reference also has a plain "Hire" text link next to its CTA (Sahali is
 * a two-sided job marketplace) — dropped here since this platform has no
 * equivalent second audience/flow to send that link to.
 */
export default function Nav() {
  return (
    <nav className="sticky top-0 z-20 border-b border-surface-border bg-background/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-8">
        <div className="flex items-center gap-2 text-foreground">
          <Logo className="h-6 w-6 text-accent" />
          <span className="text-lg font-bold tracking-tight">CompliaHub</span>
        </div>
        <div className="hidden items-center gap-8 text-sm font-medium text-foreground/70 md:flex">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="transition-colors hover:text-foreground">
              {link.label}
            </a>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Link
            href="/chat"
            className="rounded-full bg-cta px-5 py-2.5 text-sm font-semibold text-accent-foreground shadow-sm transition-transform hover:scale-105"
          >
            Enter the platform
          </Link>
        </div>
      </div>
    </nav>
  );
}

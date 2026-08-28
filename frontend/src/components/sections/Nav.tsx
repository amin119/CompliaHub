import Link from "next/link";
import Logo from "@/components/Logo";

const NAV_LINKS = [
  { href: "#labyrinth", label: "The Labyrinth" },
  { href: "#thread", label: "The Thread" },
  { href: "#evidence", label: "Evidence" },
];

/**
 * Server component (no GSAP/Lenis dependency) — the nav itself has no
 * scroll-driven behavior beyond a sticky position, so there's no reason to
 * pay for a client bundle here.
 */
export default function Nav() {
  return (
    <nav className="font-landing-sans sticky top-0 z-20 border-b border-landing-border/70 bg-landing-bg/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-8">
        <div className="flex items-center gap-2 text-landing-fg">
          <Logo className="h-5 w-5 text-landing-accent" />
          <span className="font-landing-serif text-lg tracking-tight">ComplianceHub</span>
        </div>
        <div className="hidden items-center gap-8 text-sm text-landing-fg/60 sm:flex">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="transition-colors hover:text-landing-fg">
              {link.label}
            </a>
          ))}
        </div>
        <Link
          href="/chat"
          className="border-b border-landing-accent pb-0.5 text-sm font-medium text-landing-accent transition-opacity hover:opacity-70"
        >
          Enter the platform
        </Link>
      </div>
    </nav>
  );
}

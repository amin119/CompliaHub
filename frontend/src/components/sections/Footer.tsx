import Link from "next/link";
import Logo from "@/components/Logo";

/**
 * Deliberately short. This project has no newsletter backend, no public
 * support line and no social accounts, and a footer full of dead affordances
 * would be worse than an honest one — so every link here goes somewhere that
 * actually exists.
 *
 * Section headings are sentence case rather than tracked-out uppercase: the
 * ALL-CAPS micro-label was retired across this redesign.
 */
const COLUMNS = [
  {
    heading: "Ask",
    links: [
      { label: "Chat", href: "/chat" },
      { label: "Documents", href: "/documents" },
    ],
  },
  {
    heading: "Scan",
    links: [
      { label: "Scanner", href: "/scanner" },
      { label: "How it works", href: "#how-it-works" },
    ],
  },
  {
    heading: "Explore",
    links: [
      { label: "Features", href: "#features" },
      { label: "Use cases", href: "#use-cases" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="border-t border-surface-border px-4 py-16 sm:px-8">
      <div className="mx-auto grid max-w-7xl gap-12 sm:grid-cols-2 lg:grid-cols-[1.6fr_1fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2 text-foreground">
            <Logo className="h-5 w-5 text-accent" />
            <span className="font-display text-base font-semibold">CompliaHub</span>
          </div>
          <p className="measure mt-4 text-sm leading-relaxed text-muted">
            Compliance answers grounded in your own standards, and a scanner that checks your
            code against them. Nothing is marked compliant without a person saying so.
          </p>
        </div>
        {COLUMNS.map((column) => (
          <div key={column.heading}>
            <p className="font-display text-sm font-semibold text-foreground">{column.heading}</p>
            <ul className="mt-4 flex flex-col gap-2.5">
              {column.links.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted transition-colors duration-[var(--dur-fast)] hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="mx-auto mt-16 max-w-7xl text-xs text-muted">
        CompliaHub — all rights reserved.
      </p>
    </footer>
  );
}

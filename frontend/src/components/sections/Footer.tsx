import Link from "next/link";
import Logo from "@/components/Logo";

/**
 * The reference design's footer has an email-subscribe input, a contact
 * email/phone, and social icons — dropped here rather than faked: this
 * project has no newsletter backend, no public support line, and no real
 * social accounts, and a footer full of dead or fake affordances would be
 * worse than a shorter, honest one. The two-column link layout (matching
 * the reference's multi-column structure) only lists routes/anchors that
 * actually exist.
 */
const COLUMNS = [
  {
    heading: "Platform",
    links: [
      { label: "Chat", href: "/chat" },
      { label: "Documents", href: "/documents" },
    ],
  },
  {
    heading: "Explore",
    links: [
      { label: "Showcase", href: "#showcase" },
      { label: "Features", href: "#features" },
      { label: "Use cases", href: "#use-cases" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="border-t border-surface-border px-4 py-14 sm:px-8">
      <div className="mx-auto grid max-w-6xl gap-10 sm:grid-cols-[1.3fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2 text-foreground">
            <Logo className="h-5 w-5 text-accent" />
            <span className="text-base font-bold">CompliaHub</span>
          </div>
          <p className="mt-3 max-w-xs text-sm text-muted">
            An agentic GraphRAG platform for ISO 27001, ISO 42001, and GDPR compliance
            intelligence — every answer grounded in evidence.
          </p>
        </div>
        {COLUMNS.map((column) => (
          <div key={column.heading}>
            <p className="text-xs font-bold tracking-wide text-foreground uppercase">
              {column.heading}
            </p>
            <ul className="mt-4 flex flex-col gap-2.5">
              {column.links.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="mx-auto mt-12 max-w-6xl text-center text-xs text-muted">
        CompliaHub — all rights reserved.
      </p>
    </footer>
  );
}

import Link from "next/link";
import Logo from "@/components/Logo";

/**
 * Brief §6 asks for Security/Privacy/Terms/Documentation/Contact links.
 * None of those pages exist in this project (no auth, no legal/docs
 * routes) — same adaptation made in every prior landing pass: link only to
 * what's real (`/chat`, `/documents`) rather than ship dead links.
 */
export default function Footer() {
  return (
    <footer className="font-landing-sans relative border-t border-landing-border px-4 py-10 sm:px-8">
      <div
        aria-hidden="true"
        className="bg-landing-blueprint pointer-events-none absolute inset-0 text-landing-fg opacity-[0.05]"
      />
      <div className="relative mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-xs text-landing-fg/60 sm:flex-row">
        <div className="flex items-center gap-2">
          <Logo className="h-4 w-4 text-landing-fg" />
          <span className="font-landing-serif text-sm text-landing-fg">ComplianceHub</span>
        </div>
        <p>A GraphRAG + Agentic RAG compliance intelligence platform.</p>
        <div className="flex items-center gap-5">
          <Link href="/chat" className="transition-colors hover:text-landing-fg">
            Chat
          </Link>
          <Link href="/documents" className="transition-colors hover:text-landing-fg">
            Documents
          </Link>
        </div>
      </div>
    </footer>
  );
}

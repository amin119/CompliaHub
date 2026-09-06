"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import MagneticLink from "@/components/landing/MagneticLink";
import { useMagnetic } from "@/hooks/useMagnetic";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { buttonClasses } from "@/lib/ui";

/** The product's two halves plus the ingestion route — the real
 * destinations. `Scan` is the link that previously did not exist anywhere
 * on the marketing page, which is why half the product was undiscoverable
 * from `/`. */
const PRODUCT_LINKS = [
  { href: "/chat", label: "Ask", cursor: "Ask" },
  { href: "/scanner", label: "Scan", cursor: "Scan" },
  { href: "/documents", label: "Documents", cursor: "Upload" },
];

const SECTION_LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#use-cases", label: "Use cases" },
];

export default function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const logoRef = useMagnetic<HTMLAnchorElement>(0.2, 50);

  useEffect(() => {
    // Passive scroll listener rather than a ScrollTrigger: this is app
    // chrome, not part of the scroll narrative, and it must keep working
    // on routes where Lenis/ScrollTrigger aren't mounted at all.
    function handleScroll() {
      setScrolled(window.scrollY > 24);
    }
    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // A route change or an Escape press should never leave the overlay stuck open.
  useEffect(() => {
    if (!menuOpen) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [menuOpen]);

  return (
    <>
      <nav
        className={`sticky top-0 z-50 border-b transition-all duration-[var(--dur-base)] ease-[var(--ease-out-quart)] ${
          scrolled
            ? "border-surface-border bg-background/80 backdrop-blur-md"
            : "border-transparent bg-transparent"
        }`}
      >
        <div
          className={`mx-auto flex max-w-7xl items-center justify-between px-4 transition-[padding] duration-[var(--dur-base)] sm:px-8 ${
            scrolled ? "py-3" : "py-5"
          }`}
        >
          <Link
            ref={logoRef}
            href="/"
            className="flex items-center gap-2.5 text-foreground"
            data-cursor="Home"
          >
            <Logo className="h-6 w-6 text-accent" />
            <span className="font-display text-lg font-semibold tracking-tight">CompliaHub</span>
          </Link>

          <div className="hidden items-center gap-7 text-sm lg:flex">
            {PRODUCT_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                data-cursor={link.cursor}
                className="font-medium text-foreground transition-colors hover:text-accent"
              >
                {link.label}
              </Link>
            ))}
            <span className="h-4 w-px bg-surface-border" />
            {SECTION_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-muted transition-colors hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <MagneticLink
              href="/chat"
              cursorLabel="Ask"
              className={buttonClasses({ size: "md", className: "hidden sm:inline-flex" })}
            >
              Get started
            </MagneticLink>
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              aria-label="Open menu"
              aria-expanded={menuOpen}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-surface-border text-foreground lg:hidden"
            >
              <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4">
                <path
                  d="M2.5 5h11M2.5 11h11"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
        </div>
      </nav>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.25 }}
            className="fixed inset-0 z-[60] flex flex-col bg-background p-6 lg:hidden"
          >
            <div className="flex items-center justify-between">
              <span className="font-display text-lg font-semibold text-foreground">Menu</span>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="Close menu"
                className="flex h-9 w-9 items-center justify-center rounded-full border border-surface-border text-foreground"
              >
                <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4">
                  <path
                    d="M4 4l8 8M12 4l-8 8"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>

            <div className="mt-10 flex flex-col gap-1">
              {PRODUCT_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="font-display border-b border-surface-border py-4 text-3xl font-semibold tracking-tight text-foreground"
                >
                  {link.label}
                </Link>
              ))}
              {SECTION_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="border-b border-surface-border py-3.5 text-base text-muted"
                >
                  {link.label}
                </a>
              ))}
            </div>

            <Link
              href="/chat"
              onClick={() => setMenuOpen(false)}
              className={buttonClasses({ size: "lg", className: "mt-8 w-full" })}
            >
              Get started
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

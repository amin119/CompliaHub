"use client";

import { useEffect, useState } from "react";

/**
 * A real, explicit dark-mode switch — not just following the OS
 * preference. Toggles `data-theme` on `<html>` (which both the CSS custom
 * properties and Tailwind's `dark:` variant key off, see globals.css) and
 * persists the choice to localStorage, read back by the init script in
 * layout.tsx before the next page load to avoid a flash of the wrong
 * theme. Shared by the landing page and the app shell — one switch, one
 * mechanism, for the whole product.
 */
export default function ThemeToggle() {
  // `isDark` starts `false` unconditionally — matching what the server
  // always renders (no `document` to read there) — and is corrected in
  // the effect below, once mounted, rather than read via a lazy `useState`
  // initializer that peeks at `document.documentElement.dataset.theme`
  // directly.
  //
  // That lazy-initializer version looks like the more elegant fix (and
  // silences the `react-hooks/set-state-in-effect` lint rule), but it's
  // wrong: the layout's `beforeInteractive` script really does set
  // `data-theme="dark"` before this component's first client render, so a
  // lazy initializer reading it renders the *sun* icon on the client's
  // first pass while the server-rendered HTML (embedded for hydration
  // comparison) always contains the *moon* icon's markup — a genuine
  // content mismatch, not just a cosmetic one. Confirmed live: this threw
  // a real React hydration error in the production build specifically
  // whenever the persisted theme was "dark" (never under `pnpm dev`,
  // whose hydration-mismatch handling is more lenient), and production's
  // mismatch recovery re-rendered enough of the document to wipe
  // `data-theme` right back off `<html>` a moment after paint — silently
  // breaking dark-mode persistence across a reload. Deferring the read to
  // a `useEffect` means the first client render matches the server
  // exactly; the icon then flips a frame later, which is the standard,
  // safe trade-off for anything that depends on browser-only state.
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- see comment above: this state can only be known after mount (it reads `document`), so it cannot be computed at render time.
    setIsDark(document.documentElement.dataset.theme === "dark");
  }, []);

  function toggle() {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // Storage can throw in private-browsing/locked-down contexts —
      // the toggle still works for this page view, it just won't persist.
    }
    setIsDark(next === "dark");
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-surface-border text-foreground transition-colors hover:border-accent hover:text-accent"
    >
      {isDark ? (
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
          <path
            d="M12 3v2m0 14v2m9-9h-2M5 12H3m15.4-6.4-1.4 1.4M6.6 17.4l-1.4 1.4m13.2 0-1.4-1.4M6.6 6.6 5.2 5.2"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
          <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
          <path
            d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </button>
  );
}

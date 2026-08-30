import type { Metadata } from "next";
import { Inter, Poppins } from "next/font/google";
import Script from "next/script";
import "./globals.css";

// One typeface pair for the whole product now — landing page and app
// alike (see globals.css's header comment: the earlier "landing vs app"
// token/font separation was retired once the user asked for the new
// design to cover /chat and /documents too, not just the marketing page).
const poppins = Poppins({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["600", "700"],
});

const inter = Inter({
  variable: "--font-sans-base",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CompliaHub",
  description: "GraphRAG + Agentic RAG compliance intelligence platform",
};

// Sets data-theme before hydration so there's no flash of the wrong
// theme. Tailwind's `dark:` variant is configured (globals.css) to key
// off this attribute rather than the OS media query, so it must always
// be set to something — reads the user's explicit choice from
// localStorage if they've made one, otherwise falls back to the OS
// preference, rather than leaving the attribute unset (which would make
// every `dark:` class never apply for a first-time visitor whose OS
// prefers dark).
//
// `suppressHydrationWarning` on <html> is load-bearing, not decorative:
// this script sets `data-theme` outside React's own render tree, so the
// attribute is absent from the server-rendered markup. Without the
// suppression, React 19's production hydration treats that as a real
// mismatch and recovers by discarding/re-rendering the root — which
// wipes the attribute back off right after paint (confirmed live: caught
// as a failing Playwright reload-persistence test only in a production
// build, since dev mode's hydration-mismatch handling is more lenient
// and doesn't trigger the same recovery path).
const themeInitScript = `
  (function () {
    try {
      var stored = localStorage.getItem("theme");
      var theme = stored === "dark" || stored === "light"
        ? stored
        : (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      document.documentElement.dataset.theme = theme;
    } catch (e) {}
  })();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${poppins.variable} ${inter.variable} antialiased`}
      suppressHydrationWarning
    >
      <Script id="theme-init" strategy="beforeInteractive">
        {themeInitScript}
      </Script>
      <body className="min-h-screen">{children}</body>
    </html>
  );
}

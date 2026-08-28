import type { Metadata } from "next";
import { Geist, Geist_Mono, Instrument_Serif, Inter, Playfair_Display } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// The editorial/display face used by the app itself (e.g. /chat's page
// title) — unrelated to the landing rebuild below, kept exactly as-is per
// the brief's "do not touch the existing app" instruction.
const playfairDisplay = Playfair_Display({
  variable: "--font-serif",
  subsets: ["latin"],
});

// Landing-page-only typefaces (brief §4). Deliberately separate CSS
// variables from the app's --font-sans/--font-serif above, consumed only
// via the .font-landing-sans/.font-landing-serif utility classes in
// globals.css — so introducing these can never change how /chat or
// /documents render.
const instrumentSerif = Instrument_Serif({
  variable: "--font-landing-serif",
  subsets: ["latin"],
  weight: "400",
});

const inter = Inter({
  variable: "--font-landing-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ComplianceHub",
  description: "GraphRAG + Agentic RAG compliance intelligence platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${playfairDisplay.variable} ${instrumentSerif.variable} ${inter.variable} antialiased`}
    >
      <body className="min-h-screen">{children}</body>
    </html>
  );
}

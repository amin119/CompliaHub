import Link from "next/link";
import { squareSpiral, type Point } from "@/lib/labyrinth";

const CENTER: Point = [260, 90];
const SPIRAL = squareSpiral(CENTER, 60, 8, 7);

/**
 * Brief section 13: the labyrinth reappears nearly empty, only one thread
 * remaining — a faint echo of the hero rather than a full replay of its
 * animation (the story has already been told once; this is a closing
 * image, not a second performance). "Request a demo" is not included as
 * a CTA — no demo-booking flow exists in this project; "Upload a
 * standard" (a real, working route) takes its place instead.
 */
export default function SectionFinal() {
  return (
    <section className="font-landing-sans mx-auto w-full max-w-3xl px-4 py-32 text-center sm:px-8">
      <svg
        viewBox="0 0 520 180"
        className="mx-auto mb-10 h-20 w-full max-w-xs text-landing-border opacity-40"
        aria-hidden="true"
      >
        <path
          d={SPIRAL.d}
          fill="none"
          className="stroke-landing-thread"
          strokeWidth={1}
          strokeLinejoin="round"
        />
      </svg>
      <h2 className="font-landing-serif text-4xl leading-tight font-normal text-landing-fg sm:text-5xl">
        Find the thread.
      </h2>
      <p className="mx-auto mt-5 max-w-md leading-relaxed text-landing-fg/70">
        Turn fragmented regulatory knowledge into evidence-backed intelligence.
      </p>
      <div className="mt-10 flex flex-wrap items-center justify-center gap-x-8 gap-y-4">
        <Link
          href="/chat"
          className="rounded-sm bg-landing-accent px-6 py-3 text-sm font-medium text-landing-accent-fg transition-opacity hover:opacity-90"
        >
          Explore the platform
        </Link>
        <Link
          href="/documents"
          className="border-b border-landing-fg/30 pb-0.5 text-sm font-medium text-landing-fg transition-colors hover:border-landing-accent hover:text-landing-accent"
        >
          Upload a standard
        </Link>
      </div>
    </section>
  );
}

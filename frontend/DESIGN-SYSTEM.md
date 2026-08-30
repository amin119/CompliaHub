# CompliaHub design system reference

Scope: **the whole product** — the landing page (`src/app/page.tsx` and
everything under `src/components/sections/` and `src/components/landing/`)
*and* the app shell (`/chat`, `/documents`, `src/app/(app)/*`,
`CitationChip`, `GraphView`). Through Part 8 these were deliberately
separate design systems; Part 9 unified them into one shared token set
(plus a real dark mode) at the user's explicit request, so this document
now covers both.

Rebuilt to match a reference design supplied by the user — a job-matching
platform called "Sahali" (`home page design/home page.svg` + `.png`) —
with the same structure and visual language, content adapted to this
platform. This replaces the earlier labyrinth/thread design entirely (see
docs/phase-6-frontend.md's Parts 4-7 for that history); Part 9 then
extended it app-wide and added dark mode (see Part 9's section for that
history).

## Tokens

Tokens live in `src/app/globals.css` as plain CSS custom properties on
`:root`, exposed to Tailwind via `@theme inline` (`--color-background`,
`--color-accent`, etc., mapping straight to the CSS variables below). One
set, shared by the landing page and the app shell — no `--landing-*`
prefix anymore. Light-mode colors are exact hex values pulled from the
reference SVG's own fills and gradient stops, not eyeballed from the
screenshot; dark-mode colors come from a second reference image the user
supplied (a dark variant of the same design family, "Loker").

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | `#ffffff` | `#0a0d0a` | Page background |
| `--surface` | `#f5f5f5` | `#151815` | Card/tag/button-secondary backgrounds |
| `--surface-blue` | `#f3f6ff` | `#16201a` | Tinted card backgrounds |
| `--surface-border` | `#e5e5e5` | `#262b26` | Hairlines |
| `--foreground` | `#0a0a0a` | `#f2f4f2` | Headline/body text |
| `--muted` | `#737373` | `#9aa39a` | Secondary text |
| `--accent` | `#0033ff` | `#22c55e` | Primary color — buttons, links, focus ring |
| `--purple` | `#977dff` | `#4ade80` | Gradient midpoint |
| `--pink` | `#ffccf2` | `#86efac` | Gradient end / soft washes |
| `--cta-fill` | blue→purple→pink gradient | solid `--accent` | Primary buttons, brand icon badges |
| `--marquee-fill` | same gradient as `--cta-fill` | orange gradient (`#f97316`→`#fb923c`) | Marquee bands only — deliberately its own token so it doesn't just look like a dimmed CTA in dark mode |
| `--glow-top` / `--glow-bottom-left` / `--glow-bottom-right` | pink / pink / baby-blue radial washes | single green wash top, none at the bottom | Page-level ambient background (`.bg-ambient-glow`) |

Utility classes: `.bg-cta` / `.bg-marquee` (background), `.text-gradient`
(gradient-clipped text), `.bg-ambient-glow` (the page-level glow layer,
composited from the three `--glow-*` tokens).

### Dark mode

A real toggle, not just a `prefers-color-scheme` fallback:

- `ThemeToggle.tsx` sets `document.documentElement.dataset.theme` to
  `"light"`/`"dark"` and persists the choice to `localStorage`. Shared by
  the landing nav and the app shell header — one switch for the whole
  product.
- `layout.tsx` runs a `beforeInteractive` inline script that reads
  `localStorage` (falling back to `prefers-color-scheme`) and sets
  `data-theme` before first paint, avoiding a flash of the wrong theme.
  It always sets the attribute explicitly — never leaves it unset — so a
  first-time visitor's OS dark-mode preference still resolves correctly.
- `globals.css` defines `:root[data-theme="dark"]` overrides for every
  token above, plus a `@media (prefers-color-scheme: dark)` fallback for
  the (rare) case where JS hasn't run yet.
- `@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"]
  *));` re-points Tailwind's `dark:` variant at the attribute instead of
  the media query — required once a manual toggle exists, otherwise a
  visitor's OS preference and their in-app choice could disagree and
  desync any pre-existing `dark:` class.
- **Known contrast pitfall, already hit once**: never hardcode `bg-white`
  on a surface that also uses `text-foreground`/`text-muted` — those text
  tokens go near-white in dark mode and become invisible against a literal
  white background. Use `bg-surface` or `bg-background` instead, which
  flip with the theme. (This exact bug shipped once in Part 9 — an
  "Upload a standard" button was white-on-white in dark mode — caught by
  an actual screenshot, not code review, and fixed by this rule.)

## Typography

- **Display**: Poppins, weights 600/700 (`--font-display`,
  `.font-display`) — bold headlines, used on both the landing page and
  the app's page headers (e.g. `/chat`'s "Ask CompliaHub", `/documents`'
  "Documents"). The reference's own headline text was exported as
  outlined vector paths (no `font-family` attribute survives that), so
  the exact original typeface couldn't be read back programmatically;
  Poppins was chosen as the closest common match to its bold, geometric
  letterforms.
- **Interface**: Inter (`--font-sans-base`, mapped to Tailwind's default
  `font-sans`) — body copy, nav, buttons, tags, and all app UI text.
- Both loaded via `next/font/google` in `src/app/layout.tsx`. Geist Sans/
  Mono and Playfair Display (from earlier landing-page eras) have been
  fully retired — nothing in the codebase references them anymore.

## Shape & spacing

- Corner radius: generously rounded everywhere now, landing *and* app —
  `rounded-3xl` for cards, `rounded-full` for buttons/pills/tags/chat
  bubbles. This was a landing-only rule through Part 8; Part 9 extended
  it to `/chat` (message bubbles, input, send button) and `/documents`
  (already close, no change needed), and to `CitationChip`/`GraphView`.
- Cards: `bg-surface` (or `bg-background` for the outer app shell),
  `border-surface-border`, `shadow-sm`.
- Buttons: pill-shaped, either `bg-cta` (primary) or a bordered
  `bg-surface`/`bg-background` pill (secondary).

## Motion

- **Marquee bands** (`.marquee-track`, `components/landing/Marquee.tsx`):
  a plain CSS `@keyframes` translate loop, not GSAP — it never needs to
  react to scroll position, just loop at constant speed. Separator is a
  sparkle SVG glyph (matching the dark-mode reference), not a "+".
  Respects `prefers-reduced-motion` via a media query that sets
  `animation: none`, not a JS check.
- **Hero entrance**: a `gsap.from(...)` stagger fade-up on mount
  (`.hero-reveal` elements), guarded by a `prefers-reduced-motion` check
  before creating the tween.
- **`Reveal`** (`components/landing/Reveal.tsx`): a generic
  scroll-triggered fade-up, `useGSAP` + `ScrollTrigger`, used to bring
  `SectionShowcase`/`SectionUseCases`/`SectionFinalCta` in as the user
  scrolls rather than rendering fully visible on load.
- **`AnimatedConversation`** (`components/landing/AnimatedConversation.tsx`):
  reveals a chat mockup's messages one at a time, staggered, the moment it
  scrolls into view (`scrollTrigger: { once: true }`) — used by
  `SectionDemo` and `SectionFeatures` so their chat previews read as a
  live exchange rather than a static screenshot. Falls back to showing
  everything immediately under `prefers-reduced-motion`.
- **Lenis**, still mounted (`components/landing/SmoothScroll.tsx`) purely
  for its smooth-scroll feel — no ScrollTrigger-driven scrub animations
  exist in this design, so the earlier GSAP-ticker sync code is inert
  infrastructure rather than load-bearing, but harmless to keep.
- GSAP's DrawSVG/MorphSVG/MotionPath plugins (still registered in
  `lib/gsap.ts`) are unused by this design — left registered rather than
  torn out, since removing them buys nothing and they add no runtime cost
  when unused.

## Components

| Component | File | Role |
|---|---|---|
| `Marquee` | `components/landing/Marquee.tsx` | The repeating diagonal gradient banner, sparkle separator |
| `BrowserFrame` | `components/landing/BrowserFrame.tsx` | Wraps product-preview mockups |
| `DemoCitation` | `components/landing/DemoCitation.tsx` | Non-fetching citation mock (visually matches the real `CitationChip`) |
| `AnimatedConversation` | `components/landing/AnimatedConversation.tsx` | Staggers a chat mockup's messages in on scroll |
| `Reveal` | `components/landing/Reveal.tsx` | Generic scroll-triggered fade-up wrapper |
| `SmoothScroll` | `components/landing/SmoothScroll.tsx` | Lenis wrapper, scoped to the landing page's mount lifetime |
| `ThemeToggle` | `components/ThemeToggle.tsx` | Light/dark switch, shared by the landing nav and the app shell |

## Deliberate departures from the reference (disclosed, not hidden)

The reference design is for a two-sided job marketplace and relies on
several things this platform genuinely doesn't have. Each was replaced
with something real rather than faked:

- **Hero email-capture input** → dropped; there's no waitlist/signup
  backend for it to submit to. A second real link ("See how it works")
  takes its place. The hero's two inline images (reference: photos
  between/behind words) become small icon badges instead — a
  crossed-out magnifying glass on line 1, the brand mark on line 2 — since
  no real photography exists for this platform and fabricating human
  photos would be worse.
- **"Video demo" placeholder** (a gray box with a play icon that would
  link to nothing) → replaced with an actual `BrowserFrame`-wrapped,
  `AnimatedConversation`-driven preview of the real chat interface.
- **Marketing stats** ("32k Trusted job recruiter", "1200+ Best
  Partner") → replaced with real, verifiable architectural facts ("3
  retrieval strategies", "100% answers cite a source") rather than
  invented numbers.
- **App Store / Google Play badges** → replaced with the two real routes
  (`/chat`, `/documents`).
- **Scattered document icons** in the final CTA → replaced with small
  badges naming the standards CompliaHub can actually answer questions
  about (ISO 27001 / ISO 42001 / GDPR) — naming what's supported, not
  claiming the platform itself is certified against them.
- **Footer newsletter input, contact email/phone, social icons** →
  dropped entirely; this project has no newsletter backend, no public
  support line, and no real social accounts. A shorter, honest footer
  beats one full of dead affordances.
- **Nav's "Hire" link** (Sahali is two-sided: job-seekers and
  recruiters) → dropped; this platform has no equivalent second audience
  to route to.

## Verified

- `pnpm lint` / `pnpm build`: clean.
- `pnpm exec playwright test` (**not** bare `npx playwright test` — see
  gotcha below): 6/6 passing against a real Chrome instance — real
  content renders, the hero entrance animation completes, the
  reduced-motion path shows content immediately and the marquee's
  `animation-name` computes to `none`, use-case cards link to the real
  `/chat` route, `/chat`/`/documents` carry the same design system
  (rebranded heading text confirmed), and the dark-mode toggle switches
  `data-theme` and survives a page reload via `localStorage`.
- Real screenshots taken in both themes (hero, showcase card stack,
  use-cases grid, final CTA/footer) — this is how a `bg-white`
  dark-mode contrast bug was actually caught and how its fix was
  confirmed, not just assumed from reading the JSX.
- Server-rendered HTML checked directly for every major section's real
  copy and the absence of error-page text.

**A real gotcha hit while re-running the test suite**: `npx playwright
test` failed with "Playwright Test did not expect test() to be called
here" / "two different versions of @playwright/test" — not an actual
duplicate-dependency problem (`pnpm why playwright` confirms only one
version, installed as `@playwright/test`'s own internal dependency, not a
conflicting top-level package). The real cause was `npx` resolving to a
different cached/fetched `playwright` CLI than the project's locally
installed one. Fixed by using `pnpm exec playwright test` instead, which
correctly resolves the local binary — use `pnpm exec`, not bare `npx`,
for Playwright in this project going forward.

# CompliaHub design system reference

Scope: **the whole product** — the landing page (`src/app/page.tsx` and
everything under `src/components/sections/` and `src/components/landing/`)
and the app shell (`/chat`, `/documents`, `/scanner`, `/scanner/[scanId]`,
`/scanner/[scanId]/report`, and everything under `src/app/(app)/`). One
shared token set and one shared component vocabulary across both.

This is the **third** design era for this frontend (see
`docs/phase-6-frontend.md` Parts 4-9 for the two that came before: a
labyrinth/thread motif, then a rebuild matching a job-marketplace reference
called "Sahali"). This document describes the current one — a from-scratch
redesign built from a brief, not from a supplied reference image — and
replaces every prior version of this file rather than appending to it.

## Why this redesign happened

Two problems, both named directly in the brief that started this work:

1. **The landing page never mentioned the Compliance Scanner.** Every
   previous era's copy, nav, and demo section were Ask-only — half the
   product was undiscoverable from `/`. This redesign's actual functional
   deliverable is `SectionScanner`, a new scroll-pinned section, plus a
   `/scanner` nav link and a second CTA everywhere the first one appeared.
2. **The previous palette carried two recognizable "AI-generated design"
   tells**: a near-black-plus-acid-green dark mode, and a brand that
   switched hue between themes (blue in light, green in dark) because its
   two reference images came from unrelated source files. Both are gone.

## The concept: Ink / Paper / Highlighter

CompliaHub reads documents, marks the clause that answers a question, and
highlights the finding in a scanned repository. The token system is named
for what the product actually does, not for a mood board: **ink**, **paper**,
and a **highlighter**.

Dark mode is an **inversion** of that idea — light is ink on warm paper,
dark is paper on deep violet-ink — never a hue swap. The brand stays the
same violet-indigo family in both themes, just brightened in the dark one so
it still reads against ink.

Three colors carry meaning, and only three:

- **`--accent`** (violet-indigo) — brand, interactive, links, focus.
- **`--mark`** (amber) — the highlighter: emphasis, "found," "live," "needs
  a human." The only color allowed to shout.
- **`--ai`** (teal) — machine-generated content specifically (AI
  validation/remediation output). Deliberately *outside* the brand family,
  so a person scanning a page can tell at a glance what a machine wrote
  without it competing with `--accent` for "this is clickable."

Severity and status (critical/high/medium/low, scan lifecycle, finding
status) are a **separate functional scale** — reds/oranges/ambers that must
survive print and both themes — and never borrow from the three brand
colors above. Risk color and brand color answering the same visual question
("is this dangerous?" vs. "is this interactive?") would be a real usability
bug, not just an inconsistency.

## Tokens

All tokens are plain CSS custom properties in `src/app/globals.css`, on
`:root` (light) and `:root[data-theme="dark"]` (dark), exposed to Tailwind
via `@theme inline`. No `--landing-*` prefix — one set for the whole
product.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | `#faf8f4` | `#141019` | Page background |
| `--surface` | `#f2eee6` | `#1d1726` | Panels, input backgrounds |
| `--surface-raised` | `#ffffff` | `#241c30` | Cards sitting on a panel |
| `--surface-border` | `#e3ddd1` | `#2e2639` | Hairlines — decorative dividers only |
| `--control-border` | `#94866d` | `#77698d` | Text-field/select/textarea borders (needs 3:1 per WCAG 1.4.11; `--surface-border` doesn't clear it) |
| `--foreground` | `#141019` | `#f4f1ec` | Body/headline text |
| `--muted` | `#6b6472` | `#a79fb2` | Secondary text |
| `--accent` / `--accent-strong` | `#4b21e2` / `#3a15b8` | `#9b7bff` / `#b79bff` | Brand, links, focus, primary buttons |
| `--accent-contrast` | `#ffffff` | `#160f24` | Text on a filled accent surface |
| `--accent-soft` | `#eee9fd` | `#2a213e` (opaque) | Tinted accent chips/badges |
| `--mark` / `--mark-strong` | `#ffce1f` / `#f0b800` | `#ffd84d` / `#ffc61f` | The highlighter |
| `--mark-contrast` | `#241b00` | `#241b00` | Text on a filled `--mark` surface |
| `--mark-soft` | `#fff4cf` | `#372e21` (opaque) | Tinted highlighter chips |
| `--ai` | `#0b6470` | `#4fd1c5` | Machine-generated content |
| `--ai-soft` | `#dcf2f4` | `#1d2f35` (opaque) | Tinted AI-content chips |
| `--cta-fill` | tight 2-stop `accent → accent-strong` | same | Primary buttons only |
| `--marquee-fill` | 2-stop `mark → mark-strong` | same | Marquee bands only — its own token so a band reads as a *marked strip*, not a dimmed CTA |
| `--glow-top` / `--glow-bottom-left` / `--glow-bottom-right` | subtle accent/mark washes | same, dimmer | `.bg-ambient-glow` — shown behind the hero and the final CTA **only** |
| `--noise-opacity` | `0.035` | `0.022` | Drives `.grain-overlay`, the paper-grain layer |
| `--ease-out-expo` / `--ease-out-quart` / `--ease-in-out-quint`, `--dur-fast/base/slow/hero` | — | — | The one motion vocabulary; JS (`lib/gsap.ts`'s `MOTION`) and CSS agree on the same values |

**Retired aliases** (`--purple`, `--surface-blue`, `--pink`,
`--accent-foreground`) that briefly existed mid-redesign to keep
not-yet-rewritten pages compiling are gone — every consumer was migrated to
its real semantic token (`--ai`, `--surface-raised`, `--mark-soft`,
`--accent-contrast` respectively) as each page was rewritten, and the last
one was removed once the app shell pass (Phase 3) finished.

Utility classes: `.bg-cta` / `.bg-marquee` (fills), `.text-gradient`
(gradient-clipped text, currently unused but kept for a future accent),
`.mark-block` (a static full-line highlighter background), `.mark-sweep`
(the animated variant `MarkSweep` uses — see Motion), `.mark-underline` (a
lighter marker-stroke-behind-baseline variant for inline emphasis),
`.bg-ambient-glow`, `.grain-overlay`, `.cursor-none` (added from JS only
once `Cursor` has actually mounted).

### Why `--accent-soft`/`--mark-soft`/`--ai-soft` are opaque, not translucent

They started as `rgba(...)` tints. That's the more obvious way to write a
"soft" tint, but a translucent color's *effective* contrast against text
depends on whatever surface sits behind it — and `accent` on `accent-soft`
measured 4.81:1 over `--background` but only 4.10:1 over `--surface-raised`,
failing WCAG AA (4.5:1) the moment that chip appeared on a card instead of
the page. Baking in one opaque hex value per theme keeps every chip at AA
everywhere it's used, at the cost of one extra color decision if a new
surface tone is ever added.

### A control-specific border token

`--surface-border` is a hairline: 1.27:1 against `--background` in light
mode, nowhere near the 3:1 WCAG 1.4.11 wants for a UI component's boundary.
That's fine for a decorative divider between list rows, but every real
`<input>`/`<select>`/`<textarea>` in the product (chat's message box, the
scan review form's three fields) was using it too, which meant every text
field on the page had a border a low-vision user genuinely couldn't
resolve. `--control-border` is a second, heavier line reserved for actual
form controls, verified at ≥3:1 against every surface tone it appears on.

### Dark mode mechanism

Unchanged from earlier eras, still load-bearing:

- `ThemeToggle.tsx` sets `document.documentElement.dataset.theme` and
  persists the choice to `localStorage`. One switch, shared by the landing
  nav and the app shell header.
- `layout.tsx` runs a `beforeInteractive` inline script that reads
  `localStorage` (falling back to `prefers-color-scheme`) and sets
  `data-theme` before first paint — no flash of the wrong theme.
  `suppressHydrationWarning` on `<html>` is **load-bearing, not
  decorative**: this script sets the attribute outside React's render
  tree, so it's absent from server-rendered markup; without the
  suppression, React 19's production hydration treats that as a mismatch
  and its recovery path silently wipes the attribute back off right after
  paint. Confirmed live as a real bug in a production build only — dev
  mode's more lenient mismatch handling never surfaces it.
- `@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"]
  *));` re-points Tailwind's `dark:` variant at the attribute instead of
  the OS media query.
- **Known contrast pitfall**: never hardcode `bg-white`/`text-white` (or
  any literal Tailwind gray/zinc/slate shade) on a surface that also uses
  `text-foreground`/`text-muted` — those go near-white in dark mode and
  vanish against a literal light background, or vice versa. Always route
  through a token (`bg-surface`, `bg-background`, `text-muted`) so it flips
  with the theme. `e2e/contrast.spec.ts` (see Verified) exists specifically
  because this class of bug has shipped more than once.
- **Printing forces light mode regardless of the active theme.** The
  report page's print handler (`scanner/[scanId]/report/page.tsx`)
  temporarily flips `data-theme` to `"light"` around `window.print()` and
  restores the previous value on the standard `afterprint` event — dark
  mode's literal `dark:` utility classes can't be reached by a `@media
  print` token override alone, since they key off the DOM attribute, not a
  media query.

## Typography

- **Display** — Poppins 600/700 (`--font-display`, `.font-display`, plus
  `.text-display`/`.text-h1`/`.text-h2` utilities carrying `clamp()` sizes,
  tight `line-height`, and negative `letter-spacing`). The hero headline is
  `clamp(3rem, 11vw, 11rem)` — type *is* the hero visual, not a background
  image behind it.
- **Interface** — Inter (`--font-sans-base`, Tailwind's default
  `font-sans`) — every body/UI/data string in the product.
- Both load via `next/font/google` in `layout.tsx`, used identically on the
  landing page and inside the app shell — one typeface pair for the whole
  product, not a landing/app split.
- Body copy is capped at a 62ch measure (`.measure`) wherever it appears —
  a wide, undifferentiated text column is its own kind of tell.
- **No single-word color accents inside a headline.** Emphasis comes from
  scale, weight, or a full-phrase `MarkSweep`, never from recoloring one
  word mid-sentence — a pattern common enough in AI-generated marketing
  copy to be worth naming and avoiding deliberately.

## Shape & motion vocabulary

- Corner radius: `rounded-3xl` for cards/panels, `rounded-full` for
  buttons/pills/badges/chat bubbles — everywhere, landing and app alike.
- Buttons and badges are built from shared class functions in `src/lib/ui.ts`
  (`buttonClasses`, `BADGE_BASE`, `CHIP_BASE`, `filterPillClasses`) rather
  than components — this codebase mixes `<Link>` and `<button>` for
  navigation vs. action, and a single wrapper forwarding both prop sets was
  worse than a shared string. Anything needing magnetism wraps the result
  in `MagneticLink`.
- Cards use `.card-interactive` (`components/*`, `globals.css`) for a
  uniform hover-lift (translateY + accent-tinted border/shadow) — one
  definition so every clickable card in the product, on any page, lifts
  identically.
- **Two registers, deliberately.** The landing page performs — maximal
  motion, a custom cursor, magnetic CTAs, scroll-pinned storytelling. The
  app (`/chat`, `/documents`, `/scanner/*`) is quiet and dense, because
  someone using it is reading through potentially hundreds of findings.
  `Cursor` and `MagneticLink`'s magnetic pull are **landing-only** by
  design — a custom cursor hovering an 80-row findings table would be
  actively hostile to the person reading it, not delightful.
- The one *orchestrated* sequence on the whole site is the hero's load-in
  (`Hero.tsx`): headline lines slide out of their masks, the highlighter
  sweeps the second line, then the sub/CTAs/preview settle in — measured at
  ~1.15s end-to-end (see Verified). Every other reveal is scroll-triggered,
  not timed.
- `prefers-reduced-motion` is honored at three independent layers, because
  three independent animation systems exist in this codebase and each
  needed its own gate:
  - **GSAP** — `lib/gsap.ts`'s `prefersReducedMotion()` helper, checked
    before every `gsap.from`/`ScrollTrigger.create` call; components that
    read it during *render* (not inside an effect) go through
    `useMediaQuery("(prefers-reduced-motion: reduce)")` instead, which
    renders the correct SSR snapshot rather than causing a hydration
    mismatch.
  - **Plain CSS** — a `@media (prefers-reduced-motion: reduce)` block in
    `globals.css` stops the marquee loop, the skeleton shimmer, the blink
    caret, and hides `.grain-overlay`.
  - **`motion/react`** (Framer's successor, used inside the app shell for
    tab underlines, list stagger, the chat thread pulse, etc.) — a
    product-wide `<MotionConfig reducedMotion="user">` in
    `MotionProvider.tsx`, wrapping the whole app in `layout.tsx`. This one
    was a real gap found during the Phase 4 polish pass: every
    `motion.div` in the app was animating regardless of the OS preference
    until this provider was added, because Motion's own components don't
    read the media query unless told to.

## Components

| Component | File | Role |
|---|---|---|
| `Nav` | `sections/Nav.tsx` | Landing nav — scroll-shrink, glassy, magnetic logo/CTA, mobile overlay menu with Escape handling. Carries the `/scanner` link that used to be missing entirely. |
| `Hero` | `sections/Hero.tsx` | The one orchestrated load sequence; headline via `MaskedLines` (not `RevealText` — see below), CTAs to both `/chat` and `/scanner` |
| `SectionScanner` | `sections/SectionScanner.tsx` | **New.** The functional fix for the content gap — a 7-step scroll-pinned pipeline walkthrough (Upload→Scan→Map→Validate→Remediate→Review→Report), `id="how-it-works"` |
| `SectionDemo` | `sections/SectionDemo.tsx` | The Ask half — real capabilities list + a `BrowserFrame`/`AnimatedConversation` mock of `/chat` |
| `SectionShowcase` | `sections/SectionShowcase.tsx` | The three real retrieval strategies (vector/graph/agentic), overlapping evidence-card stack |
| `SectionFeatures` | `sections/SectionFeatures.tsx` | Bento grid, 9 tiles each tagged `Ask`/`Scan`/`Both` |
| `SectionUseCases` | `sections/SectionUseCases.tsx` | Editorial numbered list (not a card grid) of real jobs people do, both halves |
| `SectionFinalCta` | `sections/SectionFinalCta.tsx` | Dual CTA close (`/chat` + `/scanner`), the page's second and last ambient glow |
| `Footer` | `sections/Footer.tsx` | Real links only — no fabricated newsletter/social/contact affordances |
| `MaskedLines` | `landing/MaskedLines.tsx` | Author-specified line breaks + GSAP mask reveal, for any heading containing a **nested component** (a `MarkSweep`, a link) |
| `RevealText` | `landing/RevealText.tsx` | SplitText-driven line-mask reveal for **plain-text-only** headings — SplitText rewrites the heading's innerHTML (and does so again via `autoSplit` on font load), which orphans anything React rendered inside it |
| `MarkSweep` | `landing/MarkSweep.tsx` | The animated highlighter: two stacked identical text layers, the marked one revealed via an animated `clip-path` (not a background-width tween — see the code comment on why that fails in dark mode) |
| `Reveal` | `landing/Reveal.tsx` | Generic scroll-triggered fade-up for non-heading blocks |
| `Marquee` | `landing/Marquee.tsx` | Repeating band; `items: string[]` + optional `reverse` |
| `Cursor` | `landing/Cursor.tsx` | Landing-only custom cursor, swells into a labelled pill via `data-cursor="…"`; disabled on coarse pointers and under reduced motion |
| `MagneticLink` | `landing/MagneticLink.tsx` | A `<Link>` that leans toward the pointer (via `useMagnetic`); degrades to a plain link on touch/reduced-motion |
| `Noise` | `Noise.tsx` | The fixed paper-grain layer, opacity driven by `--noise-opacity` |
| `MotionProvider` | `MotionProvider.tsx` | Product-wide `motion/react` reduced-motion gate (see Motion) |
| `PipelineProgress` | `PipelineProgress.tsx` | The scan's 5-track status stepper — used in `/scanner/[scanId]` |
| `PageHeader` | `PageHeader.tsx` | The shared app-shell page header — icon badge + title + description + optional actions slot, used by `/chat`, `/documents`, `/scanner` |
| `StatGrid` | `StatGrid.tsx` | A bordered row of labeled stat cards, replacing the plain inline text strips that used to sit atop the scan detail and report pages |
| `BarRow` | `BarRow.tsx` | A labeled horizontal bar for a raw count (never a percentage) — the report's severity/status/framework breakdowns |
| `ThemeToggle` | `ThemeToggle.tsx` | Light/dark switch, shared everywhere |

## `MaskedLines` vs. `RevealText` — a real bug and its fix

`RevealText` uses GSAP's `SplitText.create(el, { type: "lines", mask:
"lines", autoSplit: true })` to find line boundaries and mask-reveal them.
`autoSplit` is what makes it re-measure correctly once the display font
(Poppins) finishes loading after first paint — but doing that rewrites the
heading's `innerHTML`, which silently orphans any React-rendered element
nested inside it.

This shipped as a real, live bug on the hero headline: `MarkSweep` was
nested inside `RevealText`, so its clip-path animation ran against a DOM
node SplitText had already detached — the highlighter never swept, frozen
permanently at `inset(0 100% 0 0)`. It was caught by instrumenting the
actual computed `clip-path` in a Playwright test across the sequence, not
by reading the JSX.

The fix was structural, not a patch: `MaskedLines` takes explicit
author-specified `lines: ReactNode[]` (so it never needs to touch
`innerHTML` for the split) and is now what every heading containing a
`MarkSweep` uses (`Hero`, `SectionShowcase`, `SectionFinalCta`).
`RevealText` stays reserved for plain-text-only headings, and its file
comment says so directly.

## Deliberate departures / rules this design holds itself to

Named directly in the brief that started this redesign, checked against
during a self-critique pass, and worth restating so a future change
doesn't accidentally reintroduce them:

- **No single-word headline color accents** — see Typography.
- **The highlighter marks a full phrase, never one word** — `.mark-block`/
  `.mark-sweep` are always applied to a whole line or clause.
- **Gradients have exactly one job each**: `--cta-fill` on the primary
  button only, `--marquee-fill` on marquee bands only, `--glow-*` behind
  the hero and the final CTA only. No gradient used as generic filler
  anywhere else on the page.
- **Custom cursor and magnetic buttons are landing-only** — a deliberate
  narrowing from "landing + optionally app," because the app's quiet
  register needs to stay quiet.
- **No tracked-out ALL-CAPS eyebrow labels.** The previous `Eyebrow`
  component (a decorative uppercase micro-label) is fully removed, not
  just unused — the one place a numbered marker survives is
  `SectionScanner`'s pipeline steps, where the sequence is real.
- **Severity/status colors never borrow the brand palette** — see Tokens.
- **No aggregate compliance score anywhere**, including the printed
  report — a pre-existing project principle ("technical evidence coverage,
  not certification"), reasserted here because a redesign is exactly the
  moment a stray "94% compliant" stat tile could slip in unnoticed.
  Enforced by an explicit Playwright assertion (see Verified).

## The app-shell craft pass

The Phase 3 pass (see the two-register principle under Motion) intentionally
did a **token migration** on `/chat`, `/documents`, `/scanner`, and
`/scanner/[scanId]/**` — same layout, new colors. That was correct as far as
it went, but it left those pages reading as "a form with the new palette"
rather than something anyone would actually want to read. A follow-up pass
gave each page a real visual identity without touching its data flow, its
motion register, or any behavior already covered by `phase3-checkpoint.spec.ts`:

- **`PageHeader`** replaced every page's plain `<h1>` + description with an
  icon badge (the same colored-soft-circle language the landing page's
  empty states already used) + title + description. One component, so
  `/chat`, `/documents`, and `/scanner` all got it identically rather than
  three hand-tuned headers drifting apart over time. `/scanner/[scanId]`
  and the report page needed a bespoke variant (they carry extra actions —
  a status badge, a "View report" link, a print button — that `PageHeader`'s
  props don't model) built from the same visual pieces by hand.
- **`StatGrid`** replaced four separate "flex-wrap text strip" stat blocks
  (documents' had none; the scanner list, scan detail, and report pages
  each had their own near-identical one) with a single bordered card grid.
  The report's review-coverage block and the scan detail/report file-count
  strips are now the same component, not three copies that happened to
  agree today and would drift on the next edit.
- **`BarRow`** turned the report's three findings-breakdown tables
  (severity / status / framework) from a flat number list into real
  horizontal bars — colored to match `SeverityBadge`'s own scale for the
  severity breakdown, so the badge and the bar always agree. Deliberately
  a **count-only** visualization: each bar's width is proportional to
  `count / max **within its own category**`, never against a total and
  never rendered as a percentage — the one place this project is
  emphatic that nothing may read as an aggregate compliance score. The
  status breakdown (whose badge labels — "Requires human review",
  "Potential non-compliance" — are the longest in the product) got its own
  full-width section rather than sharing a 3-column row with severity and
  framework, once a first pass revealed those long badges had nowhere to
  fit next to a bar in a narrow column.
- Every finding card in the report gained the same severity-colored left
  border (`border-l-4`, matching `SEVERITY_BORDER`) the scan detail findings
  table already used — one visual language for "how severe is this," not
  two.
- `/chat`'s empty state gained a real intro line ("Ask it like you'd ask a
  colleague") instead of only a one-line hint, and each suggested question
  became a small card carrying the standard it maps to (a neutral tag, not
  an accent-colored one — the tag is metadata, not a second call to action)
  plus an arrow that appears on hover, so the suggestions read as
  affordances rather than static text.
- `/documents` and `/scanner`'s empty states grew from a small muted icon
  to the same 56px icon-in-a-ring treatment (`ring-8 ring-accent-soft/40`)
  used elsewhere, with a real two-line message instead of one flat
  sentence — and non-empty lists now carry a small "N uploaded this
  session" / "N scanned repositories" label above them, so the list has a
  heading the way the findings table already did.
- Document rows gained a file-extension chip (`PDF`/`DOCX`), read directly
  off the filename — a real, verifiable fact about the file, not an
  invented one.

None of this touched `src/lib/api.ts`, any data-fetching effect, the review
form, the validate/remediate flow, or the findings table's filtering logic —
`e2e/phase3-checkpoint.spec.ts` (real backend, no mocks) and the a11y/contrast
suites all still pass unmodified after this pass, which is the actual
evidence that "more designed" didn't cost "still works."

## Verified

Every claim above was checked against the running app, not just read off
the JSX — this project has been burned before by mocked/code-review-only
verification missing real infra and hydration bugs.

- `pnpm exec tsc --noEmit`, `pnpm lint`, `pnpm build`: clean.
- `pnpm exec playwright test` (**not** bare `npx playwright test` — a
  previously-documented gotcha: `npx` can resolve a different cached
  Playwright CLI than the project's own, producing a confusing "two
  different versions of @playwright/test" error even though `pnpm why
  playwright` shows only one). **37/37 passing**, across:
  - `e2e/landing.spec.ts` — real landing content renders; **both halves of
    the product are discoverable** (the `/scanner` nav link, the
    `#how-it-works` section, and more than one Ask/Scan CTA each); the
    hero entrance completes; reduced-motion shows final state instantly
    with the marquee's `animation-name` computing to `none`; use-case rows
    link to real routes; `/chat`/`/documents` share the same design
    system; dark mode toggles and survives reload.
  - `e2e/phase2-checkpoint.spec.ts` — the hero sequence measured end-to-end
    at **~1.15s** (against a 1.2s budget); dual final CTA present; light/
    dark screenshots captured.
  - `e2e/phase3-checkpoint.spec.ts` — run against the **real backend**
    (not mocked): a real streamed chat answer with citations; the history
    drawer opens, is keyboard-operable, and closes on Escape; scan-detail
    tabs switch and a finding row expands; the report renders and
    contains no aggregate compliance score; printing from dark mode
    forces light and restores dark afterward; all five app routes
    screenshotted in both themes.
  - `e2e/contrast.spec.ts` — every real foreground/background token pair
    the product renders (body text, muted text, accent links, all three
    `-soft` chip pairs, CTA label text, form-control borders, …) measured
    against WCAG AA (4.5:1 for text, 3:1 for UI boundaries) **by reading
    the live computed styles**, not a hardcoded hex table — so a future
    token edit is what this test actually re-verifies. Four real failures
    were caught and fixed this way: light-mode `--ai` at 3.87:1 on the
    page background, `--accent-soft` dropping to 4.10:1 in dark mode
    depending which surface it sat on (fixed by making the `-soft` tokens
    opaque — see Tokens), and every form control's border, which was
    reusing the 1.27:1 `--surface-border` hairline.
  - `e2e/a11y.spec.ts` — a hand-rolled sweep (no axe dependency installed)
    across all six routes: exactly one `<h1>` per page, every interactive
    control has an accessible name, every `aria-expanded` element is
    keyboard-reachable, and every `<svg>` is either named or
    `aria-hidden`. Caught and fixed **eight real unannotated decorative
    SVGs** (list-row icons on `/documents` and `/scanner`, the pipeline
    stepper's check/failure icons, the upload spinner icon, and the scan
    detail page's error icon and row-expand chevron) — all purely
    decorative next to their own text label, now `aria-hidden="true"`.
- Two more real bugs, beyond the ones already listed above, caught only by
  driving the actual rendered page rather than reading the code:
  - **The pinned scanner section could clip itself.** `SectionScanner`'s
    pinned block was taller than a laptop-sized viewport, making part of
    it permanently unreachable while `ScrollTrigger` held it pinned.
    Fixed by collapsing every step's description except the active one
    while pinned (verified at 0px overflow at 780px and 900px viewport
    heights) and falling back to the fully-expanded unpinned list under
    760px of viewport height.
  - **Completed pipeline steps were invisible.** `PipelineProgress`'s
    circle had a base `bg-background` that won a CSS specificity tie
    against the "done" state's `bg-accent`, leaving a white checkmark
    drawn on a white circle in light mode. Found from an actual
    screenshot, fixed by giving every state (failed/done/active/pending)
    its own explicit background instead of sharing one default.
  - **The report's status-badge labels overflowed their bar-chart
    column.** The first `BarRow` pass gave every label a fixed `w-28`
    column; `FindingStatusBadge`'s longer labels ("Requires human
    review", "Potential non-compliance") are wider than that at their own
    font size and `whitespace-nowrap`, so they visually overlapped the bar
    next to them. Caught from a screenshot, not the JSX. Fixed by giving
    `BarRow` a `labelWidthClassName` override and moving the status
    breakdown to its own full-width section instead of squeezing it into
    a three-column row alongside severity and framework.
- Screenshots taken in both themes across all routes as part of the above
  runs — this is how the pipeline-stepper contrast bug above was actually
  caught, the same way an earlier era's `bg-white` dark-mode bug was
  caught by a screenshot rather than code review.

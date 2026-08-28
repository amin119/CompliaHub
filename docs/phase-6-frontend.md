# Phase 6 — Frontend

Status: **Parts 1 through 5 all built.** Part 1: chat (conversation-aware,
non-streaming at the time), citation display, document upload + job-status
polling — see "Part 1 — what was built" and its "Live verification" below
(written when Grok's billing block still forced mocking the final answer
call). Part 2: answer generation moved off Grok onto Gemini, real token
streaming (with a status indicator through the agent's condense → plan →
retrieve → critique → rewrite → answer stages), and a graph visualization of
the retrieval evidence — see "Part 2" below. Part 3: a first visual redesign
— a marketing landing page, a design system, and motion throughout — see
"Part 3" below. Part 4: a full creative-direction pass on the landing page
(an "editorial/institutional" identity replacing Part 3's SaaS-gradient
look) — see "Part 4" below. Part 5: a second, larger creative-direction
pass replacing Part 4's identity entirely with a labyrinth/thread visual
metaphor (Theseus and Ariadne as the *conceptual*, not literal, foundation)
— see "Part 5" below. The app itself (`/chat`, `/documents`) had not
functionally changed since Part 2 through any of that — Parts 3-5 were all
landing-page/design-system work. Part 6: the chat page's own *visual*
design, specifically, explicitly requested by the user ("I didn't like it
at all") — see "Part 6" below. Part 7 (in progress): a full rebuild of the
landing page (only) on the exact GSAP/Lenis/d3-force stack specified by a
detailed engineering brief, discarding Part 5's `motion`-based
implementation — see "Part 7" below, which is being written and checked in
phase by phase per that brief's own explicit process requirement.

## Part 2 plan (written before building, per this project's docs workflow)

**Decision from the last AskUserQuestion round:** switch final answer
generation from Grok (xAI) to Gemini before building streaming. Reasoning:
building "streaming" and then verifying it by mocking the one thing that
would actually stream (the token-by-token answer) proves nothing real — the
whole point of this feature is watching real tokens arrive. Gemini is
already configured, free-tier, and its SDK supports `generate_content_stream`
natively, so this removes an external dependency instead of adding one.

**Streaming design:** one new `POST /query/stream` endpoint, SSE
(`text/event-stream`), consumed via `fetch()` + `ReadableStream` (not
`EventSource`, since it needs a POST body). A shared event vocabulary
(`app/services/streaming_events.py`) — `status`/`token`/`done`/`error` — is
used identically whether the question was routed to the plain vector/graph
path or the full agent loop, so the frontend handles both with one switch
statement. For the agent path specifically: LangGraph's `get_stream_writer()`
lets each node (`condense_question`, `plan`, `retrieve`, `critique`,
`rewrite_query`, `answer`) push a `status` event as it starts, and lets
`answer_node` push a `token` event per chunk as Gemini streams it — this is
the idiomatic LangGraph pattern for exposing progress from inside a node
without restructuring the graph itself, and it's a genuine no-op (not a
special case to maintain) when the graph is `.invoke()`d instead of
`.stream()`d, so the existing non-streaming `/query` route needs zero changes
to keep working.

**Graph visualization design:** `retrieval.build_graph_evidence()` turns the
`ProvenancedRelationEdge`s already gathered by local/global search into a
structural `GraphEvidence` (deduped nodes + edges) — the exact thing
`render_evidence` was previously formatting into prompt strings and
discarding. Returned on `QueryResponse.graph_evidence` (default empty, so
Part 1's vector-only answers are unaffected) and rendered client-side with
`force-graph` (canvas-based, no React peer-dependency — safer than a
React-wrapped graph library against a brand-new React 19/Next 16 stack).

## Goal

A usable chat UI: streaming answers, clickable citations back to exact
clauses, a graph visualization of the retrieval path, and document
upload/job-status views wired to the real ingestion pipeline.

## Concepts to learn first

- **Streaming responses (SSE vs WebSocket)** — the roadmap's architecture
  diagram specifies REST/SSE between frontend and backend; Server-Sent Events
  are simpler than WebSockets for one-directional (server → client) token
  streaming and are the more common pattern for LLM chat UIs.
- **Graph visualization in the browser** — rendering a traversal path (nodes
  = entities, edges = relations from Phase 4) as an interactive diagram,
  which needs a dedicated graph-layout library rather than hand-rolled SVG.
- **Optimistic / polling UI for async jobs** — document uploads kick off a
  Celery pipeline (Phase 1) that takes time; the UI needs to show progress
  without the user refreshing, which means either polling a job-status
  endpoint or subscribing to updates.

## The real scope question, resolved

The roadmap's checklist has two items — streaming and graph visualization —
that the backend doesn't actually support returning yet, not just frontend
work waiting to be built:

- **Streaming**: `/query` is synchronous — one blocking call through
  classify → retrieve → critique → rewrite → answer, returning full JSON.
  Real token streaming would need Grok's SDK `stream=True` support wired
  into `answer_generation.py` and a `StreamingResponse` on the backend
  route — and even then, most of a request's latency is the pre-answer
  agent work, not the final LLM call, so streaming only covers the last leg.
- **Graph visualization**: `QueryResponse` never returns the actual
  entities/relations a `graph`/`agent`-classified answer used —
  `graph_facts`/`community_context` are formatted into the LLM prompt as
  plain strings inside `retrieval.render_evidence` and thrown away
  afterward. Visualizing "the traversal path for this answer" needs that
  evidence structurally returned first.

Confirmed with the user up front (same Part 1/Part 2 pattern as every other
phase here): ship the fully-functional core now, treat both of those as
Part 2 since they're backend+frontend joint efforts, not frontend-only.

## Part 1 — what was built

1. **`frontend/src/lib/api.ts`** — a typed API client (`askQuestion`,
   `uploadDocument`, `getDocument`, `getDocumentChunks`) matching the
   backend's Pydantic schemas field-for-field.
2. **Chat (`frontend/src/app/page.tsx`)** — replaces the Phase 0 static
   placeholder. Holds `conversation_id` in React state and passes it back
   on every message, so a multi-turn conversation (Phase 5 Part 2) actually
   works from the browser — the classifier decides per-message whether
   there's anything to continue. "New conversation" clears it. Errors
   (e.g. the xAI billing block) render inline as a message instead of
   silently failing.
3. **Citation display (`frontend/src/components/CitationChip.tsx`)** — each
   citation is a clickable chip; clicking lazily fetches
   `GET /documents/{document_id}/chunks` and shows the matching chunk's
   real text. Required one small, deliberate backend addition (see below)
   — without it, citation display could only ever be a metadata-only stub.
4. **Document upload + job status (`frontend/src/app/documents/page.tsx`)**
   — a file input posts to `/documents`, then polls `GET /documents/{id}`
   every 3s until both `status` and `graph_status` reach a terminal state.
   There's no "list all documents" endpoint, so this only ever shows
   documents uploaded in the current browser session — a real, disclosed
   limitation, not an oversight.

### Small backend addition this required

**`Citation` gained a `document_id` field.** Without it, the frontend had
no way to know *which* document a citation's `chunk_id` belongs to —
`GET /documents/{id}/chunks` needs the document id, and `document_filename`
alone isn't a usable lookup key. `chunk.document_id` was already available
at every `Citation(...)` construction site in `retrieval.py`, so this was a
trivial, additive, backward-compatible field — not scope creep into the
Part 2 items above, just what "citation display" required to be a real
feature instead of a stub.

## Live verification

No browser-automation tool is available in this environment, so real
in-browser click-through/visual testing was **not possible** — disclosed
here rather than assumed. What *was* verified for real:

- `pnpm lint` and `pnpm build` both clean — zero TypeScript errors, both
  routes (`/`, `/documents`) compile and statically generate.
- Both pages served by the real `pnpm dev` server return the expected
  rendered content server-side (checked via direct HTTP fetch of the
  rendered HTML).
- The **exact JSON contracts** the frontend's TypeScript types depend on
  were verified against the real, live backend (Grok's final call mocked
  only where the pre-existing xAI billing block would otherwise stop it —
  everything before that ran for real):
  - `POST /query` → real `Citation` objects from the real corpus, each
    with a real `document_id`, matching the `Citation` TS type field for
    field.
  - `GET /documents/{id}/chunks` → matches the `DocumentChunk` TS type
    field for field, confirmed against a real document's 72 real chunks.
  - `GET /documents/{id}` → matches `DocumentStatus` field for field;
    this real response also had a *stale* `error_message` alongside
    `status: "ready"` (the known cosmetic quirk from Phase 1/3 docs),
    concretely confirming the UI's guard (`doc.status === "failed"` before
    showing `error_message`) is a real, necessary defense, not
    speculative.
  - `POST /documents` (multipart upload) → returns `status: "pending"`
    immediately, matching what the upload flow expects to start polling
    from.
- A real, unmodified `/query` request through the exact endpoint the
  frontend calls hit the same pre-existing xAI billing 403 documented
  since Phase 2 — confirmed via the backend log, not a new regression.

## Part 2 — what was built

1. **Answer generation moved from Grok (xAI) to Gemini**
   (`app/services/answer_generation.py`) — the `AnswerClient` Protocol kept
   its existing `messages: list[dict]` shape (system + user, unchanged
   prompt-formatting tests) but the adapter underneath is now
   `_GeminiAnswerClient`, with both `create_completion` (unchanged callers)
   and a new `stream_completion` using `generate_content_stream`. New
   `generate_answer`/`stream_answer` share one `_build_messages` helper.
   `openai` was removed from `pyproject.toml` entirely — nothing else in
   the backend used it. This is what actually made real streaming
   verifiable: the xAI account's zero-credits block had forced every
   "live" test since Phase 2 to mock this one call.
2. **`POST /query/stream`** (`app/api/routes/query.py`) — same
   classify-then-route logic as `POST /query`, but a `StreamingResponse`
   emitting SSE. A shared vocabulary (`app/services/streaming_events.py`:
   `status_event`/`token_event`/`done_event`/`error_event`, plain dicts)
   is used by both the direct vector/graph path in the route and the agent
   path — `_stream_query_events` yields events directly (kept testable
   without string-parsing), wrapped into real `data: ...\n\n` SSE frames
   only at the very last step (`_sse_encode`).
3. **`agent.stream_agent`** (`app/services/agent.py`) — the streaming
   counterpart to `run_agent`. Every node
   (`condense_question`/`plan`/`retrieve`/`critique`/`rewrite_query`/`answer`)
   pushes a `status` event via LangGraph's `get_stream_writer()` as it
   starts; `answer_node` also pushes a `token` event per chunk as it
   consumes `stream_answer`. `get_stream_writer()` is a genuine no-op when
   the graph is `.invoke()`d instead of `.stream()`d, so `answer_node`
   always sources its answer via the streaming Gemini API and just
   silently doesn't broadcast tokens on the non-streaming path — one code
   path for both, not two to keep in sync. The final `done` event (needing
   `graph_evidence`, computed from the finished checkpoint state) is
   yielded by `stream_agent` itself after the graph's own stream ends, not
   by any single node.
4. **`retrieval.build_graph_evidence`** — turns the `ProvenancedRelationEdge`s
   local/global search already gathered into deduped `GraphNode`/`GraphEdge`
   lists (`QueryResponse.graph_evidence`, default empty). This is the
   structural form of exactly what `render_evidence` was already
   formatting into prompt strings and discarding — no new retrieval, just
   not throwing the structure away this time.
5. **Frontend**: `lib/api.ts` gained `GraphEvidence` types and
   `streamQuestion()` (a `fetch()` + `ReadableStream` SSE parser — buffers
   decoded text and only emits on a full `\n\n`-terminated frame, since
   frames can split across chunks). `page.tsx` renders a per-message status
   line (mapped through `STAGE_LABELS`) while streaming, appends tokens as
   they arrive, and swaps to citations/graph once `done` lands. New
   `components/GraphView.tsx` renders `graph_evidence` with `force-graph`
   (canvas-based, no React peer-dependency, loaded via dynamic `import()`
   inside `useEffect` so it never touches SSR).

## Part 2 — live verification (real, not mocked)

Switching to Gemini didn't just unblock streaming — it turned out the xAI
billing block had been silently gating *every* answer since Phase 2, mocked
around every time. With that gone, verification here is genuinely
end-to-end, no mocking at all, run against the live docker-compose stack
(real Postgres/Neo4j/Qdrant) and a real `GEMINI_API_KEY`:

- `uv run ruff check .` clean; full backend suite **113 passed** (2 new
  failures caught and fixed first — see "A real bug this caught" below).
- `pnpm lint` / `pnpm build` clean.
- **`POST /query/stream`, vector-classified question**, real corpus
  (`ISO-27001-2013-pdf-english.pdf` + others): real `status` events
  (`classifying` → `retrieving` → `generating_answer`), a real
  multi-chunk streamed answer from Gemini citing real clause numbers, a
  `done` event with 25 real citations and populated `graph_evidence`
  (19 nodes, 21 edges) built from real local-search relations.
- **`POST /query/stream`, agent-classified question** ("what does ISO
  42001 require that ISO 27001 doesn't?"): real full status sequence
  including a genuine `rewriting_query` → second `planning`/`retrieving`/
  `critiquing` round (the critique correctly found the first pass
  insufficient), ending in a real streamed answer that correctly says the
  corpus has no ISO 42001 document rather than hallucinating one — then
  confirmed via `GET /query/conversations/{id}` that the real turn
  persisted to Postgres exactly as returned.
- **`POST /query`** (plain, non-streaming): also verified for real — no
  Grok, no mock, a real Gemini-generated answer.
- **Frontend's actual parsing logic**: `lib/api.ts`'s `streamQuestion`
  buffering/parsing algorithm was copied verbatim into a Node script and
  run against the live backend (not just eyeballing curl's raw SSE text) —
  confirmed it correctly reconstructs `status`/`token`/`done` events from
  the real wire stream.

**A real bug this caught, not a hypothetical:** the first version of
`_stream_query_events` yielded raw event **dicts** directly as the
`StreamingResponse` body, forgetting to encode them into SSE `data: ...`
strings first — `AttributeError: 'dict' object has no attribute 'encode'`,
caught immediately by `test_query_stream_returns_status_and_token_events_
ending_in_done` on the first full-suite run. Fixed by adding `_sse_encode`
as a thin wrapping generator between the event producer and
`StreamingResponse`, keeping `_stream_query_events` itself testable as
plain dicts.

**Known limitations, disclosed rather than solved:** no in-browser
click-through/visual test was possible (still no browser-automation tool
in this environment) — the SSE contract and rendering logic were verified
as above, but nobody has watched the tokens render in an actual browser
tab. `force-graph`'s TypeScript types model it as `new ForceGraph(element)`
even though the library is Kapsule-generated at runtime; this matched and
compiled cleanly, but wasn't independently cross-checked against the
library's own usage docs beyond what the shipped `.d.ts` asserts.

## Part 3 — visual redesign + landing page

Explicitly requested by the user: a genuinely aesthetic, professional visual
design with real motion, plus a marketing landing page that funnels into the
existing chat/documents product rather than dropping visitors straight into
the app. Scope was entirely frontend — no backend changes.

### Design system

- **`globals.css`** now defines real design tokens (`--surface`,
  `--surface-border`, `--accent`, `--accent-soft`, `--ring`) layered over
  the existing light/dark `--background`/`--foreground` split, exposed to
  Tailwind via `@theme inline` so `bg-surface`, `border-surface-border`,
  `text-accent`, etc. work as first-class utility classes everywhere. Fixed
  a pre-existing bug in the process: `body`'s `font-family` was hardcoded to
  `Arial, Helvetica, sans-serif`, silently never applying the Geist font
  variables the layout was already loading.
- **Palette**: indigo accent (trust/technical) paired with an emerald hint
  (verified/compliant cue) on a zinc-neutral base — a deliberate choice for
  a compliance product over something more playful.
- **`components/Logo.tsx`** — one inline SVG mark (hexagon = "the
  standard", three connected nodes inside = "the graph"), `currentColor`
  throughout so it needs no separate light/dark asset, reused in both the
  marketing nav and the app-shell nav so brand identity is consistent
  across the whole site, not just within the app.
- **`motion`** (the current name for the Framer Motion package) added as
  the animation library — chosen over hand-rolled CSS-only animation for
  anything that needs to react to state (message arrival, status changes,
  scroll position) while staying declarative in JSX; purely decorative,
  always-looping motifs (the hero's ambient glow) stayed plain CSS
  `@keyframes` instead, since a JS animation loop buys nothing for
  something that slow and that simple.

### Route restructuring

The chat UI moved from `/` to `/chat` (and `/documents` stayed at
`/documents`) using a Next.js route group, `app/(app)/`, so the URLs don't
gain an `/app` prefix while still sharing one layout:

- **`app/(app)/layout.tsx`** — the product's shell: sticky nav with the
  logo (linking back to `/`) and Chat/Documents links, an active-route pill
  indicator via `usePathname`.
- **`app/(app)/template.tsx`** — a small fade/slide-up on every navigation
  within the app shell. Deliberately a `template.tsx`, not folded into the
  layout: Next.js remounts `template.tsx` on every navigation (so the
  animation actually replays each time), while `layout.tsx` persists across
  routes by design and never would.
- **`app/page.tsx`** — now the marketing landing page (see below); the old
  chat implementation's logic moved to `app/(app)/chat/page.tsx` untouched
  functionally, restyled and re-animated only.
- **`app/layout.tsx`** (root) — stripped down to fonts/metadata only; the
  old global nav bar moved into `(app)/layout.tsx` since the landing page
  needed its own, different nav.

### The landing page

Sticky nav → hero (animated gradient-text headline, ambient CSS-drift glow
blobs, dot-grid backdrop, two CTAs into `/chat` and `/documents`) → a
feature grid (cross-standard mapping, multi-hop graph traversal, live
streaming, traceable citations) that fades up via `motion`'s
`whileInView` as it scrolls into view → a 3-step "how it works" → a final
CTA banner → footer. No fabricated content — every claim on the page
(streaming, citations, graph traversal, the classifier's routing) describes
a feature that's actually built and verified elsewhere in this doc, not
aspirational copy.

### Redesigned chat and documents pages

Functional logic in both pages is **unchanged** from Part 2 — only
presentation and interaction polish:

- **Chat**: message bubbles animate in (`motion.div` + `AnimatePresence`),
  a three-dot typing indicator replaces the old single pulsing dot, a
  blinking caret renders at the end of an in-progress streamed answer for a
  "live typing" feel, the input became a pill with a focus glow ring, and
  an empty state now offers three clickable example questions (from the
  README's own "Core use cases") instead of just static placeholder text.
- **Documents**: the upload control now supports real drag-and-drop (not
  just click-to-browse) with a drag-active highlight state, status badges
  got a small animated pulse ring while a document is still in flight, and
  list entries animate in/out via `AnimatePresence`.
- **`CitationChip`**/**`GraphView`**: restyled onto the same
  surface/accent tokens as everything else; the citation expand/collapse
  now animates height instead of snapping open.

### Verification

- `pnpm lint` and `pnpm build` both clean; build confirms all three routes
  (`/`, `/chat`, `/documents`) compile and prerender as static content.
- Server-rendered HTML fetched directly for all three routes and checked
  for the actual expected content (landing headline text, chat header,
  documents header) and the absence of any error-page text.
- Confirmed the landing nav's "Open the app" text and the app-shell nav's
  brand/links render on the correct, non-overlapping set of routes (no
  leftover nav from the old single-layout structure).
- Same disclosed limitation as Parts 1 and 2: no browser-automation tool in
  this environment, so the actual motion/animation, hover states, and
  drag-and-drop interaction were never watched running in a real browser —
  verified structurally (build, lint, rendered markup) rather than
  visually.

## Part 4 — editorial/institutional landing page redesign

The user gave a detailed, 33-point creative brief acting as creative
director: replace Part 3's landing page (indigo accent, glassmorphism-
adjacent glow blobs, rounded pill CTAs — explicitly "generic AI SaaS," and
explicitly what the brief said to avoid) with a "classical, intellectual,
institutional" identity — closer to a legal-archive/editorial-journal than
a startup's marketing site — while leaving the actual product
(`/chat`, `/documents`) untouched.

### Creative direction (defined before touching code, per the brief's own
instruction to)

- **Palette**: warm ivory/parchment background, near-black charcoal text,
  one restrained accent — old-gold/bronze — used only for CTAs, active
  states, and evidence highlights. Navy/burgundy/forest appear only as tiny
  desaturated category tags in one illustrative diagram, never as primary
  color. Deliberately not another purple/blue AI palette.
- **Type**: Playfair Display (serif, loaded site-wide via the root layout)
  for headlines/display text; the existing Geist Sans for everything else
  — same sans the app already used, so the two layers stay related rather
  than becoming two different products.
- **Signature motif**: the "Intelligence Thread" — a hairline with a slow
  gradient sweep (`globals.css`'s `.intelligence-thread`), reused as a
  section divider and inside the hero visual.
- **Motion philosophy**: slower, smaller-offset scroll reveals (0.8s,
  14px — see `components/landing/Reveal.tsx`) than Part 3's; no glow, no
  blob drift, no bounce. The one exception — the hero's document→network
  diagram — sequences on mount (staggered document reveal, then the thread
  and reasoning-chain nodes draw in left to right) rather than looping,
  matching "alive but calm."

### Mechanism: re-theme the shared tokens, don't touch the app pages

`/chat` and `/documents` are built entirely on the shared tokens introduced
in Part 3 (`bg-background`, `bg-surface`, `border-surface-border`,
`text-accent`, etc.) — so redefining those tokens in `globals.css` re-skins
the whole product to the new identity automatically. Neither page's own
code changed at all for Part 4; only `globals.css` (new palette + font
token) and `app/layout.tsx` (added the Playfair Display loader) did. This
is exactly what the brief's point 29 asked for — "the landing page should
feel like the same product, simply presented through a more artistic
lens" — achieved structurally rather than by manually re-styling two
already-built pages.

### What was built

- **`components/landing/HeroVisual.tsx`** — the hero's central visual:
  three overlapping source-document cards (one clause highlighted in
  accent, standing in for the excerpt an answer would later cite) feeding
  a left-to-right chain — Regulation → Requirement → Control → Evidence →
  Risk → Answer — via a drawn thread line, all as one staggered
  reveal-on-mount SVG/`motion` composition. This is the brief's "documents
  become a reasoning network" concept made literal, not a screenshot.
- **`components/landing/KnowledgeGraph.tsx`** — a static, hand-laid-out
  illustration of the real ontology (`app/services/ontology.py`'s
  `EntityType`s: Regulation, Article, Requirement, Policy, Control,
  Evidence, Risk), color-tagged by category. Deliberately static rather
  than force-directed: its job here is legibility as a brand illustration,
  not simulating the live per-query graph (`GraphView`, inside `/chat`,
  already does that with real data).
- **`components/landing/Thread.tsx`** / **`Reveal.tsx`** — the divider
  motif and the one scroll-reveal primitive every section shares, so the
  whole page moves with one consistent rhythm.
- **`components/landing/DemoCitation.tsx`** — a real bug caught before
  shipping, not after: the landing page's "evidence" and "ask the system"
  mockups originally reused the real `CitationChip`, which fetches
  `GET /documents/{id}/chunks` from the live backend by `document_id`.
  Since the mockups' citations (a GDPR article, a fictional
  retention-policy clause) don't correspond to real ingested documents,
  clicking one would have surfaced a genuine "clause not found" error
  right there on the landing page. `DemoCitation` is visually identical
  (same classes, same expand animation) but takes its excerpt as a plain
  prop instead of fetching — the mockup looks and behaves like the real
  thing without lying about what's live data versus illustration.
- **The full page** (`app/page.tsx`): nav → hero → "Regulation is
  everywhere, intelligence is not" (the problem) → a before/after
  transformation (fragmented documents → connected intelligence) → "How it
  thinks," the five real reasoning stages (Understand/Retrieve/Connect/
  Reason/Ground — an honest, elevated paraphrase of the real condense →
  retrieve → local+global search → critique/rewrite → answer pipeline, not
  invented capability) → an orchestration section → the evidence/trust
  mock → a product preview built from the chat page's own bubble/token
  classes → a product preview built from the documents page's own
  dropzone/badge classes → the knowledge-graph illustration → editorial
  use cases → a "who it's for" statement → a trust-principles list → a
  final CTA echoing the hero → a minimal footer.

### Two deliberate departures from the literal brief, and why

- **Nav/footer CTAs**: the brief's example nav includes "Sign in" and
  "Request a demo," and its example footer includes "Documentation,"
  "Security," "Privacy," "Terms," "Contact." None of those pages or flows
  exist in this project (no auth, no CRM/demo-booking backend, no
  docs/legal routes) — shipping them as literal links would mean dead
  links or fabricated flows. Substituted with real, working equivalents:
  the primary CTA opens the actual `/chat`, the footer links to the actual
  `/chat` and `/documents`. Same spirit (clear hierarchy, minimal nav), no
  fabricated destinations.
- **The "multi-agent orchestra" section (brief point 15)**: the brief's
  example names six specialized agent personas (Research/Retrieval/
  Compliance/Risk/Verification/Reporting Agent). The real system doesn't
  have six named agents — it has a classifier routing to one of three real
  strategies (`QueryCategory.VECTOR`/`GRAPH`/`AGENT`) and, within the agent
  path, one LangGraph loop with distinct stages. Reframed the section
  around what's actually real (a classifier orchestrating direct lookup /
  graph traversal / full agentic reasoning) rather than inventing agent
  personas — same "orchestra of intelligence" visual idea, zero fabricated
  architecture. Also skipped the brief's "Assessment: Partially compliant,
  2 requirements need attention" demo output (the real system returns
  grounded prose with citations, not a structured compliance verdict/score)
  in favor of a realistic prose-with-citations example matching what the
  product actually produces.

### Verification

- `pnpm lint` and `pnpm build` both clean; all three routes (`/`, `/chat`,
  `/documents`) still compile and prerender after the re-theme.
- Server-rendered HTML fetched directly for all three routes and checked
  for expected content (landing headlines for every major section,
  `/chat`'s and `/documents`' own headers) and the absence of error-page
  text — confirming the shared-token re-theme didn't break either existing
  page.
- The `DemoCitation` fix above was caught by re-reading the composed page
  before shipping it, specifically checking every interactive element
  against what data it would actually try to reach — not by trial and
  error against a running browser.
- Same disclosed limitation as every other frontend part: no
  browser-automation tool in this environment, so the hero's sequenced
  reveal, the scroll-triggered section fades, and the overall editorial
  feel have not been watched running in an actual browser — verified
  structurally (build, lint, rendered markup, content presence), not
  visually. This part in particular is the hardest to fully trust without
  eyes on a real render, and is worth the user's own look before treating
  it as finished.

## Part 5 — labyrinth/thread redesign

A second, larger creative brief from the user, this time replacing Part
4's identity entirely: the Theseus/Ariadne myth as a *conceptual*
foundation (never depicted literally — no gods, no fantasy styling) for
two ideas: **the labyrinth** (compliance's fragmented complexity) and
**the thread** (retrieval → evidence → traceability, the thing that
guides a visitor through that complexity). Same instruction as Part 4:
`/chat` and `/documents` stay untouched functionally.

### Creative direction

- **Palette**: kept Part 4's warm marble/ivory/charcoal base, but moved the
  single accent from bronze to a **deep Aegean blue**; bronze survives only
  as one of several muted secondary tags (alongside olive, terracotta) in
  the knowledge-map illustration.
- **Type**: kept Playfair Display + Geist Sans from Part 4 unchanged —
  already read as "ancient authority + modern precision," no reason to
  churn a typeface that already fit a second, related brief.
- **Signature visual**: a generated square-spiral labyrinth (a pure
  function of fixed constants, not a historically exact unicursal Cretan
  labyrinth — a deliberate simplification, since the brief itself asks to
  "reinterpret in an extremely modern way," not reproduce myth literally)
  with scattered knowledge-fragments, a thread that draws itself through
  the spiral on mount, then the spiral dims as a single clean line
  resolves outward — "complexity in, clarity out" as one cinematic
  sequence before any copy is read.
- **Mechanism unchanged from Part 4**: re-theme the shared tokens
  (`globals.css`) rather than touch either app page's code — `/chat` and
  `/documents` re-skinned to the new palette automatically.

### What was built

- **`components/landing/Labyrinth.tsx`** — the new hero visual described
  above. `spiralPath()` generates the spiral geometrically (decreasing
  square-spiral arm lengths) rather than hand-typed SVG coordinates, so
  it's easy to retune and guaranteed deterministic (required for a
  `"use client"` component to hydrate without a server/client mismatch —
  no `Math.random()` involved).
- **`components/landing/InteractiveChain.tsx`** — Section 3's "Follow the
  thread": Part 4's `HeroVisual` document-chain concept, evolved into a
  hoverable/focusable/clickable 6-step chain (Document → Requirement →
  Control → Evidence → Risk → Answer) that reveals a real one-line detail
  per step — reused and upgraded rather than built from scratch, since the
  underlying idea (a labeled chain with a thread through it) was already
  right. `HeroVisual.tsx` itself was deleted once nothing referenced it.
- **`components/landing/OrchestrationPaths.tsx`** — Section 4's
  "converging paths," an orchestrator node with lines to four stage nodes,
  each with a small symbol (compass/magnifying-glass/scale/checkmark).
- **`components/landing/BrowserFrame.tsx`** — a restrained three-dot
  browser-chrome wrapper around the documents/chat product-preview
  mockups, so Section 11's showcases read as "a look at the real app," not
  a floating context-less card.
- **`components/landing/KnowledgeGraph.tsx`** reused from Part 4 with one
  small palette fix: its "Regulation/Policy" category moved from navy to
  olive, since navy was now indistinguishable from the new Aegean-blue
  accent used for "Requirement/Evidence."
- **`Reveal.tsx`**, **`Thread.tsx`**, **`DemoCitation.tsx`** reused
  unchanged from Part 4 — the scroll-reveal rhythm, divider motif, and
  non-fetching citation mock were already exactly right for this brief too.

### Three deliberate, disclosed departures from the literal brief

- **"Specialized agent" personas (brief's Section 4)**: the brief's example
  names Research/Retrieval/Compliance/Risk/Verification/Reporting agents.
  As in Part 4, the real system doesn't have separate named agents — one
  classifier routes to one of three real strategies, and the agent path is
  one LangGraph loop with real internal stages. `OrchestrationPaths`
  depicts the real stages (Classify, Retrieve, Critique & Refine, Ground)
  as converging paths instead of inventing personas — same visual idea,
  zero fabricated architecture.
- **Regulatory-change monitoring (brief's Section 9)**: the brief asks to
  show "a new requirement appears... the platform identifies the impact,"
  implying automatic change-detection/impact-analysis. That capability
  doesn't exist — this system ingests documents on request, it doesn't
  monitor regulatory sources or diff versions. The section instead
  describes what's actually true: re-uploading an updated document joins
  the same graph immediately, so a stale answer is a re-ingestion away,
  not an automatic-monitoring claim.
- **Evidence field list (brief's Section 7)**: the brief lists "Source,
  Document, Article, Page, Excerpt, Date, Jurisdiction" as what a citation
  reveals. The real `Citation` schema has `document_filename`,
  `clause_number`, and the excerpt itself — no page number, date, or
  jurisdiction field exists. The evidence/trust section (and every
  `DemoCitation` mock) only shows the fields that are real.
- **Nav/footer links**: same adaptation as Part 4 — no "Sign in," "Request
  a demo," or Security/Privacy/Terms/Documentation/Contact pages exist in
  this project, so nav and footer link only to the real `/chat` and
  `/documents`.

### Verification

- `pnpm lint` and `pnpm build` both clean; all three routes still compile
  and prerender after the second re-theme.
- Server-rendered HTML fetched for `/` and checked for every major
  section's actual headline text (Navigate complexity / Compliance was
  never meant to be simple / Follow the thread / The thread isn't drawn by
  hand / Every document becomes part of the map / Ask a question, follow
  the evidence / No black boxes / Mapping a world that has no map / The
  labyrinth keeps changing / Complexity in / Find the thread) and the
  absence of error-page text; `/chat` and `/documents` re-checked too,
  confirming the second re-theme didn't break either existing page.
- Confirmed the three nav anchor targets (`#labyrinth`, `#thread`,
  `#evidence`) actually exist as section ids in the rendered HTML — an
  anchor nav to a missing id is a silent, easy-to-ship bug.
- A layering bug was caught and fixed while composing the page, before any
  build/lint run: the footer's blueprint-grid backdrop and its text
  content were on the same element, so the grid's `currentColor` styling
  and an unrelated leftover opacity div would have visually fought the
  actual footer text. Fixed by moving the grid onto its own
  `aria-hidden`, absolutely-positioned layer behind the real content.
- Same disclosed limitation as every other frontend part: no
  browser-automation tool in this environment, so the labyrinth's
  cinematic mount sequence, the interactive chain's hover states, and the
  overall feel have not been watched running in a real browser — verified
  structurally, not visually. Given how much of this brief lives in
  *timing and motion* specifically, this is the part most worth the user's
  own eyes before treating it as finished.

## Part 6 — chat page visual redesign

Parts 3-5 re-themed the shared CSS tokens and left `/chat`/`/documents`
functionally and structurally untouched — deliberately, per the explicit
"don't redesign the app" instruction in both landing briefs. The
consequence: `/chat` only ever inherited *colors* from the new brand, not
its actual visual language — it kept Part 1's original rounded-full pill
buttons/tags, rounded-2xl "chat bubble" shapes, and flat `bg-zinc-100`/
`bg-zinc-900` assistant bubbles that never got re-themed at all (they were
literal zinc classes, not the `bg-surface`/`bg-background` tokens
everything else runs on). Next to the marble/thread landing page, this
read as two different, disconnected products — reported directly by the
user as "I didn't like it at all." This time the fix is the chat page's
own markup/classes, not the shared tokens — the first explicit request in
this whole redesign arc to touch the app's actual code, not just its color
tokens.

### What changed

- **Assistant bubbles**: `bg-zinc-100`/`bg-zinc-900` (cold gray, never
  themed) → `border border-surface-border bg-background` (a bordered
  ivory/marble card, matching every other card on the site).
- **Corner language**: `rounded-2xl`/`rounded-full` (bubbles, buttons,
  suggestion tags) → `rounded-sm` everywhere, matching the brand's own
  explicit rule (Part 5's brief listed "excessive rounded corners" under
  "what not to do" — the chat page had been quietly violating its own
  brand's rule since Part 5 shipped, since nobody had touched its markup
  yet). Also fixed **`CitationChip.tsx`** and **`DemoCitation.tsx`**
  (`rounded-full` → `rounded-sm`) for the same reason — they're used on
  both the real chat page and the landing page's mocks, and the
  inconsistency existed in both places, not just `/chat`.
- **Typing indicator**: three bouncing bg-accent dots → `ThreadPulse`, a
  miniature version of the site's own `.intelligence-thread` sweep motif.
  A generic bouncing-dots indicator is what every other chat product uses;
  a moving thread is what *this* product's brand is actually about.
- **Header**: page title set in `font-serif` (Playfair Display) — the one
  place in the app that now visibly shares the landing page's display
  typeface, marking it as "the same product," while everything else
  (labels, buttons, body text) stays in Geist Sans, matching Part 4/5's
  explicit split (editorial serif for headlines, precise sans for
  interface — even inside the app, not just the marketing page).
- **"New conversation" / suggestion prompts / send button**: pill buttons
  and pill tags replaced with the same underlined-text-link and
  bordered-list patterns already used throughout the landing page, instead
  of inventing new component patterns just for chat.

### Verification

- `pnpm lint` and `pnpm build` both clean.
- Server-rendered HTML for `/chat` checked for the header text and the
  first suggestion prompt, and grepped to confirm `rounded-2xl` and
  `bg-zinc-100` no longer appear anywhere in the page.
- `/` and `/documents` re-checked to confirm untouched — this part
  intentionally scoped to `/chat`'s own file plus the two shared citation
  components, nothing else.
- Same disclosed limitation as always: no browser-automation tool, so the
  new `ThreadPulse` animation and the overall in-hand feel of the redesign
  haven't been watched running — the user's own look is what actually
  settles whether this lands better than before.

## Part 7 — GSAP/Lenis landing rebuild (in progress, phase by phase)

A detailed 10-section engineering brief specified a full rebuild of the
landing page — same labyrinth/thread concept and copy as Part 5, but on a
different technical stack: GSAP + ScrollTrigger/DrawSVGPlugin/
MorphSVGPlugin/MotionPathPlugin for scroll-driven timeline animation,
Lenis for smooth scroll, `motion` retained only for discrete hover/focus
micro-interactions, d3-force for the knowledge-map's node-position
physics. Confirmed with the user up front (`AskUserQuestion`, since a full
rebuild is a large, riskier undertaking than an incremental upgrade) that
this means discarding Part 5's `motion`-based implementation entirely,
not layering GSAP on top of it. The brief's own process (its section 0)
asks for phase-by-phase work with a check-in after each phase rather than
one silent pass — followed here exactly, including in this doc.

**Scope, confirmed by the brief's own section 0.1**: inspect the existing
repo and reuse what's there rather than introduce a second framework —
this repo is Next.js 16 (App Router)/React 19/Tailwind v4, so the brief's
"Next.js 15" default was not applied; the existing versions were kept.

### Phase 1 — dependencies, design tokens, typography, base shell (done)

- Installed `gsap`, `@gsap/react`, `lenis`, `d3-force` (+ `@types/d3-force`),
  `clsx`. Confirmed GSAP's formerly-Club plugins (`ScrollTrigger`,
  `DrawSVGPlugin`, `MorphSVGPlugin`, `MotionPathPlugin`) ship inside the
  public `gsap` package itself (no private registry auth needed) by
  checking they exist directly under `node_modules/gsap/` and resolve from
  the public npm registry — matches the brief's claim that these became
  free with the Webflow acquisition.
- **`src/lib/gsap.ts`** — registers all four plugins exactly once,
  guarded so it never runs during SSR (`ScrollTrigger` touches `window`/
  `document` at registration time). Every landing component imports `gsap`
  from here, never directly from `"gsap"`, so registration always happens
  before any tween is created.
- **Design tokens (brief section 3)**: added as `--landing-*` CSS
  variables in `globals.css`, deliberately namespaced separately from the
  app's own `--color-*`/`--font-*` tokens `/chat` and `/documents` depend
  on — consumed only through new `.font-landing-sans`/`.font-landing-serif`
  utility classes and `landing-*` Tailwind color utilities, never through
  the built-in `font-sans`/`bg-background`/etc. classes the app uses. Exact
  hex values from the brief; accent is aegean blue (buttons/links) with
  bronze reserved for the thread itself, converging to a single bronze
  accent in dark mode per the brief's own dark-mode guidance.
- **Typography (brief section 4)**: Instrument Serif + Inter added via
  `next/font/google` in the root layout, exposed as new
  `--font-landing-serif`/`--font-landing-sans` variables — additive, not a
  replacement of the Geist Sans / Playfair Display the app's own pages
  (`/chat`'s header) now depend on.
- **`components/landing/SmoothScroll.tsx`** — wraps the landing page in
  Lenis (`root`, patches `window` scroll directly — the standard choice
  for a full-page marketing site, as opposed to `root={false}`'s isolated
  scroll-container mode) synced to GSAP's own ticker (`lenis.on("scroll",
  ScrollTrigger.update)` + driving Lenis's raf via `gsap.ticker`), the
  documented GSAP+Lenis integration recipe for keeping ScrollTrigger's
  pinned/scrubbed animations in lockstep with Lenis's eased scroll
  position. Respects `prefers-reduced-motion` — skips constructing Lenis
  entirely rather than just disabling individual tweens.
- **New `components/sections/` file structure**, matching the brief's
  exact naming (`Nav`, `Hero`, `SectionLabyrinth`, `SectionThread`,
  `SectionAgents`, `SectionIngestion`, `SectionAsk`, `SectionEvidence`,
  `SectionMap`, `SectionChange`, `SectionClarity`, `SectionProduct`,
  `SectionAudience`, `SectionFinal`, `Footer`). Nav and Footer are fully
  real (brief's own honesty adaptations from Part 5 kept: no fabricated
  Sign-in/Demo/Security/Privacy links). Every other section renders its
  real, final copy from Part 5 as a static placeholder — Phases 2-5
  replace each one in place with its GSAP-driven behavior; nothing here
  is throwaway scaffolding to be deleted later.
- Deleted `components/landing/Reveal.tsx`, `Thread.tsx` (the CSS-only
  divider), and `Labyrinth.tsx` (the `motion`-based hero) — all three are
  being replaced by GSAP equivalents in Phases 2/3/7, not kept alongside
  them. `InteractiveChain.tsx`, `OrchestrationPaths.tsx`,
  `KnowledgeGraph.tsx`, `DemoCitation.tsx`, and `BrowserFrame.tsx` were
  kept — the brief explicitly carves out `motion` for exactly the kind of
  discrete hover/focus interaction `InteractiveChain`/`DemoCitation`
  already are, and the other two are plain SVG with no animation-library
  dependency to swap.

**A real, non-obvious bug hit and fixed during this phase**: `next/font/
google`'s `Instrument_Serif` requires an explicit `weight: "400"` (it
ships only one static weight) — omitting it failed the build with
"Missing weight for Instrument Serif." Also hit a genuine CSS parser
issue: a comment in `globals.css` using decorative em-dash characters and
an apostrophe (`app's`) caused Turbopack's CSS processing to fail with
"Unclosed string" at a location that didn't obviously correspond to any
real unclosed string — fixed by simplifying every comment in that file to
plain ASCII rather than spending time root-causing the lexer itself.
Noted as a real gotcha for this toolchain: keep CSS comments in this
project plain ASCII.

**Verification**: `pnpm lint`/`pnpm build` both clean; server-rendered
HTML for `/` checked for real headline text from three different
sections; `/chat` and `/documents` re-confirmed completely unaffected
(same exact rendered content as before this phase started); dev server
log checked for any SSR-time warnings/errors (none). Same disclosed
limitation as always — no browser-automation tool, so nothing GSAP/Lenis-
related has actually been watched running yet, since Phase 1 deliberately
doesn't add any animation to verify.

### Remaining phases (not started)

Phase 2 (hero GSAP timeline), Phase 3 (sections 2-10 scroll storytelling),
Phase 4 (product showcase sections 11-12 — needs real screenshots/
recordings from the user per the brief's own instruction, not fabricated
UI), Phase 5 (final CTA + footer polish), Phase 6 (performance/
accessibility/reduced-motion/responsive passes + a Lighthouse report),
plus the brief's deliverables list (a `DESIGN-SYSTEM.md` reference doc and
a Playwright smoke test) — tracked here as they complete.

## Learning checkpoint

You can watch a real answer stream token-by-token in the browser — with a
live status indicator through the agent's condense → plan → retrieve →
critique → rewrite → answer stages when it takes that path — trace its
citations back to their exact source clause, see the actual entities/
relations retrieval used as an interactive graph, and hold a real
multi-turn conversation with the agent, all without a single mocked
external call standing between the UI and a genuine model response.

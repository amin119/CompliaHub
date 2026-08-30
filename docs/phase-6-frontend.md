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
at all") — see "Part 6" below. Part 7: a full rebuild of the landing page
(only) on the exact GSAP/Lenis/d3-force stack specified by a detailed
engineering brief, discarding Part 5's `motion`-based implementation — all
6 phases plus both deliverables (`DESIGN-SYSTEM.md`, a real Playwright
smoke test verified passing against a live browser) now done — see
"Part 7" below. Part 8: the landing page rebuilt *again*, this time to
match a reference design the user supplied from a different project (a
job-matching platform, "Sahali"), discarding Part 7's labyrinth/thread
identity entirely — content adapted to this platform, every place the
reference relied on something this platform doesn't have (email capture,
app-store badges, marketing stats, social links) replaced with something
real — see "Part 8" below.

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

### Phase 2 — hero GSAP timeline (done)

`components/sections/Hero.tsx`: the brief's seven-beat story on one
`gsap.timeline()` — fragments fade in (staggered) → the labyrinth spiral
draws via DrawSVG → a marker travels the same path via MotionPath,
highlighting fragments roughly as it passes them → `clearProps` removes
DrawSVG's stroke-dasharray (a real DrawSVG/MorphSVG interaction gotcha:
morphing a path's `d` while a stale dasharray sized to the old geometry is
still set clips the stroke) → MorphSVG resolves the spiral into a clean
path → the headline/subhead/CTA settle in last. `prefers-reduced-motion`
is checked before any GSAP object is created, not just per-tween; the
resolved end-state renders via a plain opacity fade instead.

One deliberate simplification from the brief's exact 7 steps, documented
in the component itself: stages 2-3 ("connecting lines appear, then
resolve into the labyrinth") were combined into one direct DrawSVG reveal
of the labyrinth path, rather than drawing separate connector lines and
MorphSVG-ing those into the spiral — the latter needs a second
hand-authored path with a compatible point count for a few hundred
milliseconds of difference nobody would consciously register.

### Phase 3 — sections 2-10 (done)

- **SectionLabyrinth**: scroll-scrubbed (not autoplaying) DrawSVG reveal
  of a smaller spiral with real domain labels (Regulations, Requirements,
  Policies, Controls, Evidence, Risks, Audits) at its points — the thread
  draw and the label fade-in scrub against the *same* ScrollTrigger so
  they read as one reveal, not two separately-timed effects.
- **SectionThread**: reuses `InteractiveChain` (built in Part 5) rather
  than rebuilding it on GSAP — hover/focus/click micro-interaction is
  exactly what the brief's own tech-stack table reserves for `motion`.
- **SectionAgents**: `OrchestrationPaths`'s four converging paths now draw
  in via a scroll-scrubbed, staggered DrawSVG timeline instead of
  rendering statically.
- **SectionIngestion** / **SectionAsk**: `BrowserFrame`-wrapped mockups
  built from `/documents`'/`/chat`'s own real classes and copy — no real
  screenshot was available, disclosed rather than faked.
- **SectionEvidence**: the shared `<Thread />` primitive visually connects
  an answer to its citation — literally the same DrawSVG technique as the
  hero, so it reads as "the same thread," doing real work here instead of
  ambient decoration. Only real `Citation` fields shown.
- **SectionMap**: `KnowledgeGraph` rebuilt on real `d3-force` physics
  (`forceLink`/`forceManyBody`/`forceCollide`), with `fy` pinning every
  node to its tier (Regulation/Policy → Requirement/Article → Control/
  Evidence → Risk) so only horizontal position is left to the simulation —
  "roughly layered, not a free-floating hairball," per the brief. Run
  synchronously to convergence once at module load (300 ticks), not
  animated live in the browser, and with every node's initial x/y
  explicit (never left to d3-force's own defaults) so the result is
  identical between SSR and client hydration.
- **SectionChange**: reuses the same map (extended via a `overlay` render
  prop rendered *inside* `KnowledgeGraph`'s own `<svg>`/viewBox — an
  earlier draft tried a second, separately-positioned overlay `<svg>` on
  top of the whole component, which doesn't align with the graph's own
  coordinates once the legend below it is accounted for; fixed before
  shipping). Animates a new node/link appearing and the risk node pulsing,
  scroll-scrubbed. Does not claim automatic change-detection/impact-
  analysis — not a real capability — describes what's actually true
  instead (re-ingesting an updated document rejoins the same graph
  immediately).
- **SectionClarity**: the calm section, using the same `lib/labyrinth.ts`
  generator as the hero — a small spiral fades out while a clean line
  draws in, scroll-scrubbed, minimal copy, deliberately uncluttered.

**A real, non-obvious bug caught while wiring these sections**: every
reused Part-5 component (`InteractiveChain`, `BrowserFrame`,
`DemoCitation`, `KnowledgeGraph`, `OrchestrationPaths`) still referenced
the *app's* tokens (`bg-surface`, `text-accent`, `border-surface-border`,
plus a literal `.intelligence-thread` CSS class deleted back in Phase 1) —
not the new `--landing-*` tokens introduced for this rebuild. Caught by
grepping for those stale class names across `components/landing/` before
wiring the components into sections, not after shipping something that
looked like the old palette.

### Phase 4 — product showcases (done)

- **SectionProduct**: a more detailed `BrowserFrame` showcase than
  SectionIngestion/SectionAsk's lighter teasers, with a scroll-scrubbed
  subtle zoom and a side list of editorial callouts. The brief's "callout
  lines pointing at specific UI elements" became a static tick-mark list
  rather than literal SVG lines computed between two independently-
  responsive flex columns — connecting those precisely would need
  resize-observer-driven recalculation for a marginal gain over the
  simpler list; disclosed as a deliberate scope trade, not an oversight.
- **SectionAudience**: mostly complete already as static typographic
  composition; added a scroll-scrubbed stagger so the words settle in
  rather than appearing all at once.
- Same disclosed limitation as Section 3: no real screenshots/recordings
  were provided for any of these, so all three showcases are built from
  the real product's own classes/copy.

### Phase 5 — final CTA + footer (done)

**SectionFinal** now echoes the hero: a small, faded (opacity 0.4), static
spiral from the same shared generator sits above the closing headline —
a quiet echo of the opening image, not a full replay of its animation
("the story's already been told once"). Footer was already built in
Phase 1 (blueprint-grid backdrop, real links only — no fabricated Sign-in/
Demo/Security/Privacy pages).

### Phase 6 — performance, accessibility, reduced-motion, responsive (done)

- **Reduced-motion audit**: every file using `useGSAP`/`ScrollTrigger`
  checked for a guard (`Hero`, `SectionAudience`, `SectionChange`,
  `SectionClarity`, `SectionLabyrinth`, `SectionProduct`,
  `OrchestrationPaths`, `SmoothScroll`, `Thread`) — confirmed present in
  all nine, not just assumed.
- **Focus states**: `.font-landing-sans :focus-visible` sets a 2px
  `--landing-accent` outline, scoped under the landing root wrapper so it
  can never affect `/chat`/`/documents` focus styling.
- **Contrast**, computed by hand against the real WCAG relative-luminance
  formula (not just eyeballed): charcoal/marble ≈14.3:1, aegean/marble
  ≈10.4:1 (both clear AAA), bronze/marble ≈4.2:1 (clears 3:1 for
  graphics, fails 4.5:1 for small text) — confirmed bronze is *only* ever
  used decoratively (strokes/fills on SVG, never as text) by grepping
  every `landing-thread` usage site, so the one color that would fail a
  small-text check is never used as one. Dark-mode bronze-as-text
  (`--landing-accent` in dark mode) checked separately: ≈8.1:1, clears AA.
- **A real methodology mistake caught and fixed**: the first Lighthouse
  pass ran against the **dev server** and reported Performance 70 with
  1,070ms Total Blocking Time and 8.5s Time-to-Interactive — numbers that
  would have failed the brief's own ~85 bar. Dev mode ships unminified
  code and extra React dev-mode overhead and is never representative;
  re-ran against a real `pnpm build && pnpm start` production server and
  got **Performance 88, Accessibility 94, Best Practices 100, SEO 100**
  (Total Blocking Time 160ms, CLS 0, Speed Index 1.5s) — a legitimate
  result that actually clears the brief's target. Largest Contentful
  Paint still reports 3.6s at the top-line metric despite Lighthouse's own
  LCP-breakdown insight showing the actual LCP element (the hero subhead)
  rendering with only ~174ms of measured delay — an unresolved
  discrepancy in Lighthouse's own numbers, disclosed rather than chased
  further once the overall category score already cleared the target.
- **Bundle-size check**: real production chunk sizes inspected directly
  (largest individual chunk 224KB) rather than guessed at; considered
  `next/dynamic(..., {ssr:false})`-splitting `KnowledgeGraph` per the
  brief's suggestion, but `SectionChange` needs its synchronous
  `NODE_BY_ID` export to position an overlay node — forcing that split
  would mean duplicating the d3-force layout computation or restructuring
  the coupling for a d3-force simulation over 10 nodes that's already
  microseconds of work. Skipped as not worth the complexity; documented
  as a deliberate call, not silently dropped.

### Deliverables

- **`DESIGN-SYSTEM.md`** (repo root of `frontend/`): tokens, type scale,
  motion principles, component map, known limitations, and the verified
  metrics above, all in one reference doc for future landing-page work.
- **`e2e/landing.spec.ts`** + **`playwright.config.ts`**: a real Playwright
  smoke test, run against a real Chrome instance (pointed at an existing
  local Chrome install rather than downloading Playwright's own browser
  binaries for one test file) — confirms the page renders with real
  content, the hero's GSAP timeline actually completes (not just that the
  page loaded — asserts `.hero-copy` reaches `opacity: 1`, which only
  happens once the full timeline resolves), the `prefers-reduced-motion`
  path shows the resolved state almost immediately instead of waiting
  through the full sequence, and `/chat`/`/documents` are unaffected.
  **All 4 tests pass** — this is the first point in the whole GSAP rebuild
  where the animation behavior itself was verified running for real,
  rather than only through code review, since no browser-automation tool
  was available for most of this rebuild's history.

## Part 8 — reference-design rebuild ("Sahali")

The user supplied a real reference design from a different project — a
job-matching platform called "Sahali," as both an SVG (`home page
design/home page.svg`, vector paths, ~2.8MB) and a full-page PNG
screenshot (1600×5123) — and asked for the landing page to follow it
structurally and visually, with content adapted to this platform. This
discards Part 7's labyrinth/thread identity entirely; the app itself
(`/chat`, `/documents`) is untouched, same standing rule as every prior
landing-page pass.

### Extracting the actual design, not eyeballing a screenshot

The SVG's own vector data was inspected directly rather than guessed from
the PNG: `grep`-ing for hex colors and gradient stops pulled the exact
palette (`#0033FF` → `#977DFF`/`#AA99F6` → `#FFCCF2`, a 3-stop
blue-purple-pink gradient used throughout) and common `rx` (corner-radius)
values, confirming a heavily-rounded, pill-and-card visual language. The
one thing that *couldn't* be recovered this way: the reference's text had
been exported as outlined vector paths (no `font-family` survives that
conversion), so the original typeface couldn't be read back
programmatically — Poppins was chosen as the closest common match to its
bold, geometric headline lettering, disclosed as an approximation rather
than asserted as a confirmed match.

### What was rebuilt

- **Tokens/fonts** (`globals.css`, `layout.tsx`): a new `--landing-*`
  palette matching the extracted colors, `--landing-gradient` as one
  reusable variable for the signature blue→purple→pink gradient, Poppins
  (display) + Inter (interface) replacing Instrument Serif — same
  namespacing discipline as every prior pass, so `/chat`/`/documents`
  stay wired to their own tokens throughout.
- **Deleted**: every labyrinth/thread-specific component and the
  `lib/labyrinth.ts` generator (`Thread`, `KnowledgeGraph`,
  `OrchestrationPaths`, `InteractiveChain`) — none of these concepts exist
  in the new design; kept `BrowserFrame` and `DemoCitation` (still useful,
  restyled to the new rounder tokens).
- **New `components/landing/Marquee.tsx`** — the reference's repeating
  diagonal gradient banner, a plain CSS keyframe loop (not GSAP — it never
  needs scroll-position awareness), respecting `prefers-reduced-motion`
  via a media query rather than a JS check.
- **All new section components** (`Hero`, `SectionDemo`,
  `SectionShowcase`, `SectionFeatures`, `SectionUseCases`,
  `SectionFinalCta`, restyled `Nav`/`Footer`/`Eyebrow`) matching the
  reference's exact structure: hero → marquee → demo → showcase (floating
  card + checklist) → features (stats + chat mockup) → use-cases grid (6
  cards) → final CTA card → marquee → footer.

### Six deliberate departures from the reference, each disclosed

The reference is for a two-sided job marketplace and relies on several
things this platform genuinely doesn't have — each replaced with
something real rather than faked, not silently dropped:

1. **Hero email-capture input** → removed (no waitlist backend); a real
   second link ("See how it works") takes its place.
2. **"Video demo" placeholder** (a gray box with a non-functional play
   icon) → replaced with an actual `BrowserFrame`-wrapped preview of the
   real chat interface — more honest *and* more informative than a fake
   video button.
3. **Marketing stats** ("32k Trusted job recruiter", "1200+ Best
   Partner") → replaced with real, verifiable facts ("3 retrieval
   strategies," "100% answers cite a source") instead of invented
   numbers — this project's standing rule against fabricated statistics
   applies exactly the same to a borrowed design's stat slots as to
   original copy.
4. **App Store / Google Play badges** → replaced with the two real
   routes (`/chat`, `/documents`).
5. **Footer newsletter input, contact email/phone, social icons** →
   dropped; no newsletter backend, no public support line, no real
   social accounts exist for this project.
6. **Nav's "Hire" link** (Sahali's second, recruiter-side audience) →
   dropped; no equivalent second flow exists here.

### Verification

- `pnpm lint`/`pnpm build`: clean.
- Server-rendered HTML checked for every major section's real copy
  (headline, showcase, features, use-cases, final CTA) and the absence of
  error-page text; `/chat`/`/documents` reconfirmed unaffected.
- **Playwright suite rewritten** for the new content and run for real:
  5/5 passing, confirming real content renders, the hero's entrance
  animation actually completes, the reduced-motion path both shows
  content immediately *and* actually stops the marquee loop
  (`animation-name: none`, not just assumed), and a use-case card's "Ask
  now" link genuinely points at `/chat`.
- **A real gotcha hit while re-running the suite**: bare `npx playwright
  test` failed with a confusing "two different versions of
  @playwright/test" error. Not an actual duplicate-dependency bug —
  `pnpm why playwright` confirmed only one version, correctly nested
  under `@playwright/test`'s own dependency tree — the real cause was
  `npx` resolving to a different cached/fetched `playwright` CLI than the
  project's local install. Fixed with `pnpm exec playwright test`
  instead; documented in `DESIGN-SYSTEM.md` as the correct invocation for
  this project going forward.
- Docker stack and the backend API were found down at the start of this
  session (an unrelated environment restart between sessions, not caused
  by this work) — restarted and reconfirmed healthy alongside the
  frontend changes, so the full app (not just the landing page) was left
  in a verified-working state.

## Part 9 — feedback round: unification, dark mode, and polish

Following Part 8, the user sent one large, consolidated feedback message
(14 points) covering both the reference-design fit-and-finish and a scope
expansion: the new design should also reach `/chat` and `/documents`
(reversing every prior pass's "don't touch the app" rule), plus a real
dark mode using a second reference image (`original-...webp`, a dark
variant of the same reference family called "Loker" — near-black
background, bright green accent, orange marquee).

### Token unification (landing + app merged)

Every prior pass kept the landing page's tokens (`--landing-*`) separate
from the app's own tokens specifically so `/chat`/`/documents` stayed
unaffected. Extending the design to the app made that separation the
wrong call — `globals.css` was rewritten so there is now exactly one
token set (`--background`, `--surface`, `--surface-blue`,
`--surface-border`, `--foreground`, `--muted`, `--accent`, `--purple`,
`--pink`, `--cta-fill`, `--marquee-fill`, `--glow-*`), shared by both.

### Dark mode

- `:root[data-theme="dark"]` overrides every token with the Loker
  reference's palette — not just a dimmed copy of the light palette:
  accent goes from blue (`#0033ff`) to green (`#22c55e`), the marquee
  gradient goes from blue/purple/pink to orange, and the ambient glow
  drops the pink/blue corner washes for a single subdued green wash.
- `ThemeToggle.tsx` (new) sets `data-theme` on `<html>` and persists the
  choice to `localStorage`; a `beforeInteractive` `<Script>` in
  `layout.tsx` reads it back before first paint to avoid a flash of the
  wrong theme, and always sets `data-theme` explicitly (never leaving it
  unset) so a first-time visitor's OS dark-mode preference still resolves
  to the attribute-based variant.
- `@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"]
  *));` in `globals.css` re-points Tailwind's `dark:` variant at the
  attribute instead of `prefers-color-scheme` — needed because the app
  pages' existing `dark:` classes predate the toggle and would otherwise
  desync the moment a visitor's OS preference and in-app choice disagree.
- **A real contrast bug found and fixed during verification, not just
  planned around**: several card/button surfaces (`BrowserFrame`,
  `DemoCitation`, `SectionUseCases`, `SectionShowcase`,
  `SectionFinalCta`) used a literal `bg-white` — invisible against
  `text-foreground`'s near-white dark-mode value once the toggle was
  switched (an actual white-on-white button was caught in a screenshot,
  not assumed fixed). Replaced with the theme-aware `bg-surface`/
  `bg-background` tokens throughout; re-verified with a fresh screenshot
  showing legible text in both themes.

### Design fixes from the feedback list

- **Hero** (`Hero.tsx`): the headline is now two explicit non-wrapping
  flex rows sized with `clamp(1.5rem,6.5vw,3.75rem)` — guaranteed exactly
  2 lines at every supported width instead of accidentally wrapping to
  4 on some viewports. A second inline icon badge (a crossed-out
  magnifying glass, representing "not keyword search") was added to line
  1, matching the reference's pattern of one inline image per line; no
  fabricated human photography was used, since none exists for this
  platform — small icon badges stand in for it, consistent with this
  project's honesty rule.
- **Marquee** (`Marquee.tsx`): the "+" separator is now a sparkle SVG
  glyph (matching the dark-mode reference's own separator), and the band
  uses a new `bg-marquee` class/`--marquee-fill` token instead of
  `bg-cta`, so it can carry a different palette in dark mode (orange)
  instead of just inheriting the CTA's blue/green.
- **`AnimatedConversation.tsx`** (new): a small scroll-triggered,
  staggered-reveal wrapper used by both `SectionDemo` and
  `SectionFeatures`'s chat mockups, so the "conversation" plays out
  message-by-message the first time it scrolls into view rather than
  rendering as a static screenshot — animates once (not on every
  re-entry), respects `prefers-reduced-motion`.
- **`SectionShowcase`**: grew from 2 to 3 evidence cards (ISO 27001, ISO
  42001, GDPR), stacked at varied rotations/offsets/z-index for a
  deliberately "messy" overlapping look instead of a clean side-by-side
  pair, matching the reference.
- **`SectionUseCases`**: icons upgraded from plain thin-line strokes to
  duotone (filled base shape + stroked/filled detail layer), with each
  card's badge tint rotating through the accent/purple/pink palette
  instead of one uniform color.
- **`SectionFinalCta`**: the four scattered plain document icons were
  replaced with three small badges naming the standards CompliaHub can
  actually answer questions about (ISO 27001 / ISO 42001 / GDPR) — a
  label naming what's supported, carefully not a claim that the platform
  itself is certified against them (this project's standing "no fabricated
  certifications" rule).
- **`Reveal.tsx`** (new): a generic scroll-fade-in primitive, wired into
  `SectionShowcase`, `SectionUseCases`, and `SectionFinalCta` (`SectionDemo`/
  `SectionFeatures` use `AnimatedConversation` instead, which already
  reveals on scroll) so the page doesn't feel static past the hero.
- **Ambient background glow** (`page.tsx`, `.bg-ambient-glow` in
  `globals.css`): one page-level absolutely-positioned gradient layer —
  pink wash behind the hero, pink/blue (light) or subdued green (dark)
  washes at the very bottom corners behind the footer — with every
  middle section carrying its own opaque `bg-background` wrapper so the
  glow only shows where the reference shows it (top and bottom), not
  bleeding through the plain-white middle sections.
- **App pages** (`/chat`, `/documents`, `CitationChip`, `GraphView`,
  the `(app)` layout): brand renamed to "CompliaHub" throughout;
  `font-serif` → `font-display`, `rounded-sm` → `rounded-3xl`/
  `rounded-full`/`rounded-2xl` to match the landing page's rounder shape
  language; `ThemeToggle` added to the app shell's header.

### A real hydration bug found only under a production build

The dark-mode persistence test (toggle → reload → still dark) passed
against the dev server but **failed consistently against a real
`pnpm build && pnpm start`** — `data-theme` reverted to unset right after
reload. Root cause, confirmed by instrumenting a throwaway debug test
with `page.on("pageerror", ...)`: `ThemeToggle.tsx`'s lazy `useState`
initializer read `document.documentElement.dataset.theme` directly during
the client's first render — but the server (no `document`) always
rendered the "light" (moon-icon) branch. When the persisted theme was
"dark", the client's first-hydration output (sun icon) genuinely differed
from the server-rendered markup embedded for hydration comparison — a
real content mismatch (React error #418), not just an extra/unrecognized
attribute. React 19's production hydration-mismatch recovery then
re-rendered enough of the document to wipe `data-theme` back off `<html>`
moments after paint — silently breaking persistence. Dev mode never
surfaced this because dev's mismatch handling is more lenient and doesn't
trigger the same recovery path — **a second confirmed case in this
project of dev-server behavior masking a real bug that only shows up in
production** (the first was Part 7's Lighthouse score). Fixed by reverting
`ThemeToggle` to compute `isDark` deterministically as `false` on first
render (matching what the server always renders) and correcting it in a
`useEffect` after mount instead — the standard safe pattern for anything
that depends on browser-only state, at the cost of one harmless
post-hydration re-render. This reintroduces the `react-hooks/
set-state-in-effect` lint warning that an earlier pass deliberately
avoided by switching *to* the lazy initializer — resolved with a targeted,
commented `eslint-disable-next-line`, since this is exactly the case that
rule's general advice doesn't cover (state that can only be known after
mount because it reads `document`). Also added `suppressHydrationWarning`
on `<html>` in `layout.tsx` as defensive belt-and-suspenders for the
(harmless, confirmed non-erroring) `data-theme` attribute mismatch on the
root element itself.

### Verification

- `pnpm lint` / `pnpm build`: clean.
- Playwright suite updated for the brand rename and extended with a new
  dark-mode test (toggle switches `data-theme`, survives a reload via
  `localStorage`); run **against a real production build**
  (`pnpm build && pnpm start`, not the dev server — required to catch the
  hydration bug above), repeated 3x to rule out a flake: **18/18 passing**
  (6 tests × 3 repeats), including the updated app-pages check (now
  framed as "carry the same design system" rather than "unaffected,"
  reflecting the scope reversal).
- Real screenshots taken (light and dark, top/showcase/use-cases/bottom)
  via a throwaway Playwright script, not just assumed correct from
  reading the JSX — this is how the `bg-white` contrast bug above was
  actually caught, and how the fix was confirmed.

## Learning checkpoint

You can watch a real answer stream token-by-token in the browser — with a
live status indicator through the agent's condense → plan → retrieve →
critique → rewrite → answer stages when it takes that path — trace its
citations back to their exact source clause, see the actual entities/
relations retrieval used as an interactive graph, and hold a real
multi-turn conversation with the agent, all without a single mocked
external call standing between the UI and a genuine model response.

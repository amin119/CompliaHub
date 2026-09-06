"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  deleteConversation,
  getConversation,
  streamQuestion,
  type Citation,
  type GraphEvidence,
  type StreamEvent,
} from "@/lib/api";
import CitationChip from "@/components/CitationChip";
import GraphView from "@/components/GraphView";
import Logo from "@/components/Logo";

type Message = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  graphEvidence?: GraphEvidence;
  status?: string;
  isError?: boolean;
};

const STAGE_LABELS: Record<string, string> = {
  classifying: "Classifying question…",
  condensing_question: "Understanding follow-up…",
  planning: "Planning retrieval…",
  retrieving: "Retrieving evidence…",
  critiquing: "Checking evidence…",
  rewriting_query: "Refining search…",
  generating_answer: "Writing answer…",
};

const SUGGESTIONS = [
  "What controls satisfy GDPR Article 32?",
  "What does ISO 42001 require that ISO 27001 doesn't?",
  "What controls mitigate the risk of unauthorized access?",
];

type ConversationSummary = {
  id: string;
  title: string;
  updatedAt: string; // ISO
};

const HISTORY_STORAGE_KEY = "compliahub:chat-history";
const MAX_HISTORY_ITEMS = 50;

/** No accounts/auth exist anywhere in this project (see docs/phase-8-scaling.md),
 * so history is browser-scoped via localStorage, same limitation `/documents`
 * already discloses — not synced across devices, cleared if site data is cleared. */
function loadHistory(): ConversationSummary[] {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ConversationSummary[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(history: ConversationSummary[]) {
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
  } catch {
    // Can throw (private browsing, quota) — history is a convenience, not
    // critical, so a save failure is silently ignored rather than surfaced.
  }
}

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

/** A miniature version of the site's "thread" motif (see globals.css's
 * `.intelligence-thread`) standing in for a typing indicator — a moving
 * thread rather than generic bouncing dots, so even the "thinking" state
 * carries the brand's own visual language instead of a stock chat-app cue. */
function ThreadPulse() {
  return (
    <span className="relative inline-block h-px w-6 overflow-hidden bg-surface-border align-middle">
      <motion.span
        className="absolute inset-y-0 w-1/2 bg-accent"
        animate={{ x: ["-100%", "150%"] }}
        transition={{ duration: 1.3, repeat: Infinity, ease: "easeInOut" }}
      />
    </span>
  );
}

/**
 * Only visible on hover (`group-hover/message`) — a low-friction way to
 * grab a finished answer without adding permanent chrome to every bubble.
 * Not shown while a message is still streaming/status-only.
 */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can fail (permissions, insecure context) — the
      // button just silently stays in its un-copied state, no error UI
      // for something this low-stakes.
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label="Copy answer"
      className="absolute -top-2.5 -right-2.5 flex h-6 w-6 items-center justify-center rounded-full border border-surface-border bg-surface text-muted opacity-0 shadow-sm transition-opacity group-hover/message:opacity-100 hover:text-accent"
    >
      {copied ? (
        <svg viewBox="0 0 16 16" fill="none" className="h-3 w-3">
          <path
            d="M3.5 8.5 6.5 11.5 12.5 4.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : (
        <svg viewBox="0 0 16 16" fill="none" className="h-3 w-3">
          <rect x="5.5" y="5.5" width="7" height="7" rx="1.3" stroke="currentColor" strokeWidth="1.4" />
          <path
            d="M3.5 10V4.3A0.8 0.8 0 0 1 4.3 3.5H10"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      )}
    </button>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [historyNote, setHistoryNote] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Loaded once on mount — reading localStorage during render would differ
  // between server and client and break hydration.
  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  // Escape closes the history drawer, the same way the landing nav's mobile
  // menu does — an overlay you can only dismiss with the mouse is a trap.
  useEffect(() => {
    if (!showHistory) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowHistory(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showHistory]);

  function upsertHistory(id: string, firstQuestion: string) {
    setHistory((prev) => {
      const existing = prev.find((c) => c.id === id);
      const title = existing?.title ?? firstQuestion.slice(0, 60);
      const next = [
        { id, title, updatedAt: new Date().toISOString() },
        ...prev.filter((c) => c.id !== id),
      ].slice(0, MAX_HISTORY_ITEMS);
      saveHistory(next);
      return next;
    });
  }

  // Only auto-scroll when the user is already near the bottom — otherwise
  // a long answer streaming in would keep yanking them back down while
  // they're scrolled up reading an earlier message or a citation.
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceFromBottom < 150) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  async function submitQuestion(question: string) {
    if (!question || loading) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "", status: "classifying" },
    ]);
    setInput("");
    setLoading(true);

    function updateLastMessage(update: (message: Message) => Message) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = update(next[next.length - 1]);
        return next;
      });
    }

    function handleEvent(event: StreamEvent) {
      if (event.type === "status") {
        updateLastMessage((message) => ({ ...message, status: event.stage }));
      } else if (event.type === "token") {
        updateLastMessage((message) => ({
          ...message,
          status: undefined,
          content: message.content + event.text,
        }));
      } else if (event.type === "done") {
        setConversationId(event.conversation_id);
        upsertHistory(event.conversation_id, question);
        updateLastMessage((message) => ({
          ...message,
          status: undefined,
          citations: event.citations,
          graphEvidence: event.graph_evidence,
        }));
      } else if (event.type === "error") {
        updateLastMessage((message) => ({
          ...message,
          status: undefined,
          content: event.message,
          isError: true,
        }));
      }
    }

    try {
      await streamQuestion(question, conversationId, handleEvent);
    } catch (error) {
      updateLastMessage((message) => ({
        ...message,
        status: undefined,
        content: error instanceof Error ? error.message : "Something went wrong.",
        isError: true,
      }));
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    void submitQuestion(input.trim());
  }

  function startNewConversation() {
    setMessages([]);
    setConversationId(null);
    setHistoryNote(null);
  }

  async function openConversation(id: string) {
    setHistoryNote(null);
    setLoading(true);
    try {
      const conversation = await getConversation(id);
      setMessages(
        conversation.turns.flatMap((turn) => [
          { role: "user" as const, content: turn.question },
          { role: "assistant" as const, content: turn.answer },
        ]),
      );
      setConversationId(id);
      setShowHistory(false);
    } catch {
      // Expected, not a bug: only `agent`-classified turns ever persist
      // anything (see the `getConversation` doc comment in lib/api.ts) —
      // a saved conversation whose every turn was a quick factual/relational
      // lookup, or a greeting, has nothing on the backend to reopen.
      setHistoryNote(
        "That conversation can't be reopened — only in-depth research questions build resumable history; quick lookups don't.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function removeFromHistory(id: string, event: React.MouseEvent) {
    event.stopPropagation();
    setHistory((prev) => {
      const next = prev.filter((c) => c.id !== id);
      saveHistory(next);
      return next;
    });
    try {
      await deleteConversation(id);
    } catch {
      // Best-effort — the entry is already gone from the visible list
      // either way, and a stale/never-persisted backend thread cleaning up
      // one turn late isn't worth surfacing an error for.
    }
    if (id === conversationId) {
      startNewConversation();
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-background">
      <div className="flex w-full max-w-2xl flex-1 flex-col px-4 py-8 sm:py-10">
        <header className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
              Ask CompliaHub
            </h1>
            <p className="mt-1 text-sm text-muted">
              Answered from the ISO 27001, ISO 42001 and GDPR documents you&rsquo;ve ingested.
            </p>
          </div>
          <div className="mt-1.5 flex shrink-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setShowHistory(true)}
              aria-label="Conversation history"
              className="flex items-center gap-1.5 rounded-full border border-surface-border bg-surface px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-accent/40 hover:text-accent"
            >
              <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
                <path
                  d="M8 4.5V8l2.5 1.5M14 8A6 6 0 1 1 4.6 3.1"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M2 3v3h3"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              History
            </button>
            <AnimatePresence>
              {messages.length > 0 && (
                <motion.button
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={startNewConversation}
                  className="shrink-0 border-b border-accent/40 pb-0.5 text-xs font-medium text-accent transition-opacity hover:opacity-70"
                >
                  New conversation
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </header>

        <AnimatePresence>
          {historyNote && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="mb-4 flex items-start justify-between gap-3 rounded-2xl border border-surface-border bg-surface px-4 py-2.5 text-xs text-muted"
            >
              <span>{historyNote}</span>
              <button
                type="button"
                onClick={() => setHistoryNote(null)}
                aria-label="Dismiss"
                className="shrink-0 text-muted hover:text-accent"
              >
                ✕
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <main
          ref={scrollRef}
          className="themed-scroll flex flex-1 flex-col gap-5 overflow-y-auto rounded-3xl border border-surface-border bg-surface p-5 sm:p-6"
        >
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="m-auto flex max-w-sm flex-col items-center gap-6 text-center"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-soft">
                <Logo className="h-6 w-6 text-accent" />
              </div>
              <p className="text-sm text-muted">
                Ask about cross-standard mapping, gap analysis, or a specific clause.
              </p>
              <motion.div
                className="flex w-full flex-col gap-2"
                initial="hidden"
                animate="show"
                variants={{ show: { transition: { staggerChildren: 0.06 } } }}
              >
                {SUGGESTIONS.map((suggestion) => (
                  <motion.button
                    key={suggestion}
                    variants={{
                      hidden: { opacity: 0, y: 6 },
                      show: { opacity: 1, y: 0 },
                    }}
                    whileHover={{ y: -1 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => void submitQuestion(suggestion)}
                    className="rounded-2xl border border-surface-border bg-surface-raised px-3.5 py-2.5 text-left text-xs text-muted transition-colors duration-[var(--dur-fast)] hover:border-accent/40 hover:text-accent"
                  >
                    {suggestion}
                  </motion.button>
                ))}
              </motion.div>
            </motion.div>
          )}
          <AnimatePresence initial={false}>
            {messages.map((message, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
                className={
                  message.role === "user"
                    ? "ml-auto max-w-[80%] rounded-3xl rounded-br-md bg-cta px-4 py-2.5 text-sm text-accent-contrast"
                    : `group/message relative mr-auto max-w-[85%] rounded-3xl rounded-bl-md border px-4 py-2.5 text-sm ${
                        message.isError
                          ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200"
                          : "border-surface-border bg-surface-raised text-foreground"
                      }`
                }
              >
                {message.role === "assistant" && message.content && !message.status && (
                  <CopyButton text={message.content} />
                )}
                {message.status ? (
                  <div className="flex items-center gap-3 py-0.5 text-muted">
                    <ThreadPulse />
                    <span className="text-xs">
                      {STAGE_LABELS[message.status] ?? message.status}
                    </span>
                  </div>
                ) : (
                  <p className="leading-relaxed whitespace-pre-wrap">
                    {message.content}
                    {loading && index === messages.length - 1 && message.role === "assistant" && (
                      <span className="animate-blink-caret ml-0.5 inline-block h-3.5 w-[2px] -translate-y-0.5 bg-current align-middle" />
                    )}
                  </p>
                )}
                {message.citations && message.citations.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5 border-t border-surface-border pt-3">
                    {message.citations.map((citation) => (
                      <CitationChip key={citation.chunk_id} citation={citation} />
                    ))}
                  </div>
                )}
                {message.graphEvidence && <GraphView evidence={message.graphEvidence} />}
              </motion.div>
            ))}
          </AnimatePresence>
        </main>

        <form onSubmit={handleSubmit} className="mt-4 flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={loading}
            placeholder="Ask about a control, clause, or gap analysis…"
            className="flex-1 rounded-full border border-surface-border bg-surface px-4 py-2.5 text-sm text-foreground transition-shadow placeholder:text-muted focus:border-accent/50 focus:ring-2 focus:ring-accent-soft focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          />
          <motion.button
            type="submit"
            disabled={loading || !input.trim()}
            aria-label="Send"
            whileTap={{ scale: 0.92 }}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-cta text-accent-contrast shadow-[0_10px_30px_-16px_var(--accent)] transition-opacity enabled:hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4">
              <path
                d="M4 10h12M11 5l5 5-5 5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </motion.button>
        </form>
      </div>

      <AnimatePresence>
        {showHistory && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowHistory(false)}
              // The scrim is the page's own ink, not a raw black — in dark
              // mode a black wash over a near-black ground reads as nothing.
              className="fixed inset-0 z-40 bg-[color-mix(in_srgb,var(--foreground)_35%,transparent)]"
            />
            <motion.aside
              role="dialog"
              aria-modal="true"
              aria-label="Conversation history"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="fixed inset-y-0 left-0 z-50 flex w-full max-w-xs flex-col border-r border-surface-border bg-background p-4 shadow-xl"
            >
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-display text-lg font-semibold text-foreground">History</h2>
                <button
                  type="button"
                  onClick={() => setShowHistory(false)}
                  aria-label="Close history"
                  className="flex h-7 w-7 items-center justify-center rounded-full text-muted hover:text-accent"
                >
                  ✕
                </button>
              </div>
              <p className="mb-3 text-xs text-muted">
                Only in-depth research conversations are resumable — quick lookups start fresh
                each time. Saved on this device only.
              </p>
              <div className="themed-scroll flex-1 space-y-1.5 overflow-y-auto">
                {history.length === 0 ? (
                  <p className="mt-8 text-center text-sm text-muted">No conversations yet.</p>
                ) : (
                  history.map((conversation) => (
                    // Two sibling buttons rather than a clickable div with a
                    // button inside it: the row has to be reachable by
                    // keyboard, and a button can't nest inside a button.
                    <div
                      key={conversation.id}
                      className={`card-interactive group/history flex items-center justify-between gap-2 rounded-2xl border px-3 py-2.5 text-sm ${
                        conversation.id === conversationId
                          ? "border-accent/40 bg-accent-soft text-accent"
                          : "border-surface-border bg-surface text-foreground"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => void openConversation(conversation.id)}
                        className="min-w-0 flex-1 cursor-pointer text-left"
                      >
                        <span className="block truncate">{conversation.title}</span>
                        <span className="block text-xs text-muted">
                          {formatRelativeTime(conversation.updatedAt)}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={(event) => void removeFromHistory(conversation.id, event)}
                        aria-label="Delete conversation"
                        className="shrink-0 rounded-full p-1 text-muted opacity-0 transition-opacity group-hover/history:opacity-100 hover:text-red-500 focus-visible:opacity-100"
                      >
                        <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
                          <path
                            d="M3.5 4.5h9M6.5 4.5V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1.5M6 7.5v4M10 7.5v4M4 4.5l.6 8a1 1 0 0 0 1 .9h4.8a1 1 0 0 0 1-.9l.6-8"
                            stroke="currentColor"
                            strokeWidth="1.3"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </button>
                    </div>
                  ))
                )}
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

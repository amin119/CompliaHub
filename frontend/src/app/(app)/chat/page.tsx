"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { streamQuestion, type Citation, type GraphEvidence, type StreamEvent } from "@/lib/api";
import CitationChip from "@/components/CitationChip";
import GraphView from "@/components/GraphView";

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

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
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
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-background">
      <div className="flex w-full max-w-2xl flex-1 flex-col px-4 py-8 sm:py-10">
        <header className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-normal tracking-tight text-foreground">
              Ask CompliaHub
            </h1>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              ISO 42001 · ISO 27001 · GDPR — answered from your ingested standards.
            </p>
          </div>
          <AnimatePresence>
            {messages.length > 0 && (
              <motion.button
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={startNewConversation}
                className="mt-1.5 shrink-0 border-b border-accent/40 pb-0.5 text-xs font-medium text-accent transition-opacity hover:opacity-70"
              >
                New conversation
              </motion.button>
            )}
          </AnimatePresence>
        </header>

        <main
          ref={scrollRef}
          className="flex flex-1 flex-col gap-5 overflow-y-auto rounded-3xl border border-surface-border bg-surface p-5 sm:p-6"
        >
          {messages.length === 0 && (
            <div className="m-auto flex max-w-sm flex-col items-center gap-6 text-center">
              <p className="text-sm text-zinc-400 dark:text-zinc-600">
                Ask about cross-standard mapping, gap analysis, or a specific clause.
              </p>
              <div className="flex w-full flex-col">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => void submitQuestion(suggestion)}
                    className="border-b border-surface-border py-2.5 text-left text-xs text-zinc-500 transition-colors last:border-0 hover:text-accent dark:text-zinc-400"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
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
                    ? "ml-auto max-w-[80%] rounded-3xl rounded-br-md bg-cta px-4 py-2.5 text-sm text-accent-foreground"
                    : `mr-auto max-w-[85%] rounded-3xl rounded-bl-md border px-4 py-2.5 text-sm ${
                        message.isError
                          ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
                          : "border-surface-border bg-background text-foreground"
                      }`
                }
              >
                {message.status ? (
                  <div className="flex items-center gap-3 py-0.5 text-zinc-500 dark:text-zinc-400">
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
            className="flex-1 rounded-full border border-surface-border bg-surface px-4 py-2.5 text-sm text-foreground placeholder:text-zinc-400 transition-shadow focus:border-accent/50 focus:ring-2 focus:ring-accent-soft focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            aria-label="Send"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-cta text-accent-foreground transition-opacity enabled:hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
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
          </button>
        </form>
      </div>
    </div>
  );
}

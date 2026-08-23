"use client";

import { useState } from "react";
import { askQuestion, type Citation } from "@/lib/api";
import CitationChip from "@/components/CitationChip";

type Message = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isError?: boolean;
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);

    try {
      const response = await askQuestion(question, conversationId);
      setConversationId(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.answer, citations: response.citations },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: error instanceof Error ? error.message : "Something went wrong.",
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function startNewConversation() {
    setMessages([]);
    setConversationId(null);
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <div className="flex w-full max-w-2xl flex-1 flex-col px-4 py-8">
        <header className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-zinc-950 dark:text-zinc-50">
              ComplianceHub
            </h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Ask about ISO 42001, ISO 27001, or GDPR compliance.
            </p>
          </div>
          {messages.length > 0 && (
            <button
              onClick={startNewConversation}
              className="shrink-0 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-900"
            >
              New conversation
            </button>
          )}
        </header>

        <main className="flex flex-1 flex-col gap-4 overflow-y-auto rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          {messages.length === 0 && (
            <p className="m-auto max-w-sm text-center text-sm text-zinc-400 dark:text-zinc-600">
              e.g. &ldquo;What controls satisfy GDPR Article 32?&rdquo; or &ldquo;What does ISO
              42001 require that ISO 27001 doesn&apos;t?&rdquo;
            </p>
          )}
          {messages.map((message, index) => (
            <div
              key={index}
              className={
                message.role === "user"
                  ? "ml-auto max-w-[80%] rounded-lg bg-zinc-900 px-4 py-2 text-sm text-zinc-50 dark:bg-zinc-100 dark:text-zinc-900"
                  : `mr-auto max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                      message.isError
                        ? "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
                        : "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                    }`
              }
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
              {message.citations && message.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5 border-t border-zinc-200 pt-2 dark:border-zinc-700">
                  {message.citations.map((citation) => (
                    <CitationChip key={citation.chunk_id} citation={citation} />
                  ))}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="mr-auto flex max-w-[80%] items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-zinc-400" />
              Thinking…
            </div>
          )}
        </main>

        <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={loading}
            placeholder="Ask about a control, clause, or gap analysis…"
            className="flex-1 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-950 placeholder:text-zinc-400 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

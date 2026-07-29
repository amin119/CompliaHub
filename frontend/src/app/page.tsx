type PlaceholderMessage = {
  role: "user" | "assistant";
  content: string;
};

const PLACEHOLDER_MESSAGES: PlaceholderMessage[] = [
  {
    role: "user",
    content: "What controls satisfy GDPR Article 32?",
  },
  {
    role: "assistant",
    content:
      "This is a placeholder chat UI (Phase 0). Real answers, streaming, and citations back to exact clauses arrive in Phase 6 once retrieval and the agent loop exist.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <div className="flex w-full max-w-2xl flex-1 flex-col px-4 py-8">
        <header className="mb-6">
          <h1 className="text-xl font-semibold text-zinc-950 dark:text-zinc-50">
            ComplianceGraph
          </h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            ISO 42001 / ISO 27001 / GDPR compliance assistant — chat UI placeholder.
          </p>
        </header>

        <main className="flex flex-1 flex-col gap-4 overflow-y-auto rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          {PLACEHOLDER_MESSAGES.map((message, index) => (
            <div
              key={index}
              className={
                message.role === "user"
                  ? "ml-auto max-w-[80%] rounded-lg bg-zinc-900 px-4 py-2 text-sm text-zinc-50 dark:bg-zinc-100 dark:text-zinc-900"
                  : "mr-auto max-w-[80%] rounded-lg bg-zinc-100 px-4 py-2 text-sm text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
              }
            >
              {message.content}
            </div>
          ))}
        </main>

        <form className="mt-4 flex gap-2">
          <input
            type="text"
            disabled
            placeholder="Ask about a control, clause, or gap analysis… (wired up in Phase 6)"
            className="flex-1 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-950 placeholder:text-zinc-400 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50"
          />
          <button
            type="submit"
            disabled
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

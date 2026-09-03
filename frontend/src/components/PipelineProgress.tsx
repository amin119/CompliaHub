"use client";

import { motion } from "motion/react";

export type PipelineStage = {
  key: string;
  label: string;
  status: string; // "not_started" | "<in-progress value>" | "ready" | "failed" | ...
};

const TERMINAL = new Set(["ready", "failed"]);

function StepIcon({ state }: { state: "done" | "failed" | "active" | "pending" }) {
  if (state === "done") {
    return (
      <motion.svg
        viewBox="0 0 16 16"
        fill="none"
        className="h-3.5 w-3.5"
        initial={{ scale: 0.5, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 400, damping: 20 }}
      >
        <path
          d="M3.5 8.5 6.5 11.5 12.5 4.5"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </motion.svg>
    );
  }
  if (state === "failed") {
    return (
      <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
        <path
          d="M4.5 4.5 11.5 11.5M11.5 4.5 4.5 11.5"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  if (state === "active") {
    return (
      <motion.span
        className="block h-1.5 w-1.5 rounded-full bg-current"
        animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
        transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
      />
    );
  }
  return <span className="block h-1.5 w-1.5 rounded-full bg-current opacity-40" />;
}

/**
 * A horizontal step tracker for the scan's five independent status tracks
 * (`status`/`findings_status`/`privacy_status`/`ai_status`/
 * `iso27001_status`) — replaces a single line of "extracting…" text with
 * something that actually shows where a multi-minute pipeline currently
 * is, since each stage genuinely runs sequentially (see the backend's own
 * chain ordering). Stages are always rendered in their fixed pipeline
 * order regardless of which ones happen to be "not_started" yet, so the
 * shape never jumps around as statuses arrive.
 */
export default function PipelineProgress({ stages }: { stages: PipelineStage[] }) {
  const doneCount = stages.filter((s) => s.status === "ready").length;
  const hasFailed = stages.some((s) => s.status === "failed");
  const fillPercent = stages.length <= 1 ? 100 : (doneCount / (stages.length - 1)) * 100;

  return (
    <div className="mb-6 rounded-2xl border border-surface-border bg-surface px-4 py-5 sm:px-6">
      <div className="relative flex items-start justify-between">
        {/* Track + fill sit behind the step circles, spanning center-to-center. */}
        <div className="absolute top-3 right-3 left-3 h-px bg-surface-border" />
        <motion.div
          className={`absolute top-3 left-3 h-px ${hasFailed ? "bg-red-400" : "bg-accent"}`}
          initial={false}
          animate={{ width: `calc(${Math.min(fillPercent, 100)}% - 0.75rem)` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />

        {stages.map((stage) => {
          const isFailed = stage.status === "failed";
          const isDone = stage.status === "ready";
          const isActive = !isDone && !isFailed && stage.status !== "not_started";
          const state: "done" | "failed" | "active" | "pending" = isFailed
            ? "failed"
            : isDone
              ? "done"
              : isActive
                ? "active"
                : "pending";

          return (
            <div key={stage.key} className="relative z-10 flex w-full flex-col items-center gap-2">
              <motion.div
                initial={false}
                animate={{
                  scale: isActive ? 1.1 : 1,
                }}
                transition={{ duration: 0.2 }}
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 bg-background transition-colors duration-300 ${
                  isFailed
                    ? "border-red-400 text-red-500"
                    : isDone
                      ? "border-accent bg-accent text-accent-foreground"
                      : isActive
                        ? "border-accent text-accent"
                        : "border-surface-border text-muted"
                }`}
              >
                <StepIcon state={state} />
              </motion.div>
              <span
                className={`max-w-[5.5rem] text-center text-[11px] leading-tight font-medium ${
                  isFailed
                    ? "text-red-500"
                    : isDone || isActive
                      ? "text-foreground"
                      : "text-muted"
                }`}
              >
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export { TERMINAL as PIPELINE_TERMINAL_STATUSES };

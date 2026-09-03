"use client";

import { useState } from "react";
import { motion } from "motion/react";

type Props = {
  accept: string;
  uploading: boolean;
  idleLabel: string;
  uploadingLabel?: string;
  hint?: string;
  onFile: (file: File) => void;
};

/**
 * Shared drag-and-drop upload zone for /documents and /scanner — the two
 * pages previously hand-rolled near-identical dropzones (same markup,
 * same drag-state handling, only the accept type/labels differed). One
 * component now, so a polish pass (this one) only has to happen once and
 * both pages stay visually identical by construction, not by convention.
 */
export default function UploadDropzone({
  accept,
  uploading,
  idleLabel,
  uploadingLabel = "Uploading…",
  hint,
  onFile,
}: Props) {
  const [dragActive, setDragActive] = useState(false);

  function handleDrop(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) onFile(file);
  }

  function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onFile(file);
    event.target.value = "";
  }

  return (
    <motion.label
      onDragOver={(event) => {
        event.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={handleDrop}
      animate={dragActive ? { scale: 1.015 } : { scale: 1 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      className={`group relative mb-6 flex cursor-pointer flex-col items-center justify-center gap-3 overflow-hidden rounded-2xl border-2 border-dashed p-10 text-sm transition-colors duration-200 ${
        dragActive
          ? "border-accent bg-accent-soft text-accent"
          : uploading
            ? "border-accent/30 bg-surface text-muted"
            : "border-surface-border bg-surface text-muted hover:border-accent/40 hover:bg-accent-soft/40"
      }`}
    >
      {/* Ambient sweep across the zone while an upload is in flight — a
          quieter, more specific "something is happening" cue than the
          bouncing icon alone, and reads clearly at a glance. */}
      {uploading && (
        <motion.div
          className="pointer-events-none absolute inset-0 -z-0"
          style={{
            background:
              "linear-gradient(100deg, transparent 30%, var(--accent-soft) 50%, transparent 70%)",
            backgroundSize: "200% 100%",
          }}
          animate={{ backgroundPosition: ["150% 0", "-150% 0"] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
        />
      )}

      <motion.div
        className="relative flex h-12 w-12 items-center justify-center rounded-full bg-background shadow-sm"
        animate={
          uploading
            ? { y: [0, -3, 0] }
            : dragActive
              ? { scale: 1.08 }
              : { scale: 1, y: 0 }
        }
        transition={
          uploading
            ? { duration: 1, repeat: Infinity, ease: "easeInOut" }
            : { duration: 0.15 }
        }
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-accent">
          {uploading ? (
            <motion.path
              d="M12 4a8 8 0 1 0 8 8"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              animate={{ rotate: 360 }}
              transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
              style={{ originX: "12px", originY: "12px" }}
            />
          ) : (
            <path
              d="M12 16V4m0 0 4 4m-4-4-4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
        </svg>
      </motion.div>

      <div className="relative flex flex-col items-center gap-0.5 text-center">
        <span className="font-medium text-foreground">
          {uploading ? uploadingLabel : dragActive ? "Drop it here" : idleLabel}
        </span>
        {hint && !uploading && <span className="text-xs text-muted">{hint}</span>}
      </div>

      <input
        type="file"
        accept={accept}
        onChange={handleChange}
        disabled={uploading}
        className="hidden"
      />
    </motion.label>
  );
}

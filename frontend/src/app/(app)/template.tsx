"use client";

import { motion } from "motion/react";

/**
 * `template.tsx` (unlike `layout.tsx`) remounts on every navigation, which
 * is exactly what a per-page enter transition needs — `layout.tsx` persists
 * across route changes so it can't replay an animation on its own.
 */
export default function AppTemplate({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex flex-1 flex-col"
    >
      {children}
    </motion.div>
  );
}

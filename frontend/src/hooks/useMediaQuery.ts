"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * Subscribes to a media query the way React actually wants external state
 * read: `useSyncExternalStore` rather than `useState` + an effect. That
 * avoids the cascading-render the `react-hooks/set-state-in-effect` rule
 * warns about, gives a correct SSR snapshot (always `false` — the server has
 * no viewport or input device), and, unlike a one-shot read on mount, keeps
 * responding if the user changes their reduced-motion preference or moves to
 * a different input device mid-session.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    [query],
  );

  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  );
}

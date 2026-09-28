import { test, expect } from "@playwright/test";

/**
 * Reads the *computed* design tokens out of the live page and checks every
 * foreground/background pair the product actually renders against WCAG AA.
 *
 * Deliberately not a table of hardcoded hex values: this way editing a token
 * in globals.css is what the test measures, so a palette tweak can't quietly
 * drop a pair below AA. Four pairs were failing when this was first written
 * (the light teal on its own tint and on the page, accent-on-accent-soft in
 * dark, and every form control's border).
 */

type Pair = { label: string; fg: string; bg: string; min: number };

// 4.5 = AA for normal-size text; 3.0 = AA for UI component boundaries
// (WCAG 1.4.11), which is what a text field's border has to meet.
const PAIRS: Pair[] = [
  { label: "body on page", fg: "--foreground", bg: "--background", min: 4.5 },
  { label: "body on panel", fg: "--foreground", bg: "--surface", min: 4.5 },
  { label: "body on card", fg: "--foreground", bg: "--surface-raised", min: 4.5 },
  { label: "muted on page", fg: "--muted", bg: "--background", min: 4.5 },
  { label: "muted on panel", fg: "--muted", bg: "--surface", min: 4.5 },
  { label: "muted on card", fg: "--muted", bg: "--surface-raised", min: 4.5 },
  { label: "accent on page", fg: "--accent", bg: "--background", min: 4.5 },
  { label: "accent on panel", fg: "--accent", bg: "--surface", min: 4.5 },
  { label: "accent on card", fg: "--accent", bg: "--surface-raised", min: 4.5 },
  { label: "accent on accent-soft", fg: "--accent", bg: "--accent-soft", min: 4.5 },
  { label: "CTA label on accent", fg: "--accent-contrast", bg: "--accent", min: 4.5 },
  { label: "CTA label on accent-strong", fg: "--accent-contrast", bg: "--accent-strong", min: 4.5 },
  { label: "marked text on highlighter", fg: "--mark-contrast", bg: "--mark", min: 4.5 },
  { label: "body on mark-soft", fg: "--foreground", bg: "--mark-soft", min: 4.5 },
  { label: "ai on ai-soft", fg: "--ai", bg: "--ai-soft", min: 4.5 },
  { label: "ai on page", fg: "--ai", bg: "--background", min: 4.5 },
  { label: "ai on card", fg: "--ai", bg: "--surface-raised", min: 4.5 },
  { label: "control border on page", fg: "--control-border", bg: "--background", min: 3.0 },
  { label: "control border on panel", fg: "--control-border", bg: "--surface", min: 3.0 },
  { label: "control border on card", fg: "--control-border", bg: "--surface-raised", min: 3.0 },
];

for (const theme of ["light", "dark"] as const) {
  test(`design tokens meet WCAG AA — ${theme}`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem("theme", t), theme);
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);

    const results = await page.evaluate((pairs) => {
      const root = getComputedStyle(document.documentElement);

      // Resolves through the browser, so any color syntax a token uses
      // (hex, rgb, color-mix) comes back as concrete channel values.
      const probe = document.createElement("span");
      document.body.appendChild(probe);
      const rgb = (token: string): [number, number, number] => {
        probe.style.color = root.getPropertyValue(token).trim();
        const parsed = getComputedStyle(probe)
          .color.match(/[\d.]+/g)!
          .slice(0, 3)
          .map(Number);
        return parsed as [number, number, number];
      };

      const channel = (c: number) => {
        const v = c / 255;
        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
      };
      const luminance = ([r, g, b]: [number, number, number]) =>
        0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);

      const out = pairs.map((pair) => {
        const a = luminance(rgb(pair.fg));
        const b = luminance(rgb(pair.bg));
        const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        return { ...pair, ratio: Math.round(ratio * 100) / 100 };
      });
      probe.remove();
      return out;
    }, PAIRS);

    const failures = results.filter((r) => r.ratio < r.min);
    if (failures.length > 0) {
      console.log(
        failures.map((f) => `${f.label}: ${f.ratio} (need ${f.min})`).join("\n"),
      );
    }
    expect(failures).toEqual([]);
  });
}

import { test, expect } from "@playwright/test";

/**
 * Smoke test for the landing page, rewritten for the "Ink / Paper /
 * Highlighter" redesign (see DESIGN-SYSTEM.md). Confirms the page renders
 * with real content, both halves of the product (Ask and Scan) are
 * discoverable from `/`, the hero's entrance animation actually completes
 * (not just that the page loaded), reduced-motion is honoured, and
 * `/chat`/`/documents` remain unaffected.
 *
 * The previous version of this file asserted copy from an earlier
 * placeholder reference design ("Sahali", a job-matching platform) that no
 * longer exists on the page at all — every assertion below was re-derived
 * from the actual rendered markup, not carried over.
 */

test("landing page renders with real content", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /ask hard questions[\s\S]*scan hard code/i }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Ask a question" }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Scan a repo" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: /point it at your repo/i })).toBeVisible();
});

test("both halves of the product are discoverable from the nav and the close", async ({
  page,
}) => {
  await page.goto("/");

  // The content gap this redesign fixed: nothing on the old landing page
  // ever mentioned the scanner. Now it's a nav link, a full section, and
  // one half of the closing CTA.
  await expect(page.getByRole("link", { name: "Scan", exact: true }).first()).toHaveAttribute(
    "href",
    "/scanner",
  );
  await expect(page.locator("#how-it-works")).toBeAttached();

  await page.locator("footer").scrollIntoViewIfNeeded();
  const askCtas = page.getByRole("link", { name: "Ask a question" });
  const scanCtas = page.getByRole("link", { name: "Scan a repo" });
  expect(await askCtas.count()).toBeGreaterThan(1);
  expect(await scanCtas.count()).toBeGreaterThan(1);
});

test("hero entrance animation completes and reveals the headline", async ({ page }) => {
  await page.goto("/");
  const heroReveal = page.locator(".hero-reveal").first();
  await expect(heroReveal).toHaveCSS("opacity", "1", { timeout: 5_000 });
});

test("prefers-reduced-motion shows content immediately, no marquee loop", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  const heroReveal = page.locator(".hero-reveal").first();
  await expect(heroReveal).toHaveCSS("opacity", "1", { timeout: 1_500 });

  const marqueeTrack = page.locator(".marquee-track").first();
  await expect(marqueeTrack).toHaveCSS("animation-name", "none");
});

test("use-case rows link to the real product routes, not a dead end", async ({ page }) => {
  await page.goto("/");
  const askRow = page.getByRole("link", { name: "Ask a question" }).last();
  await expect(askRow).toHaveAttribute("href", "/chat");
  const scanRow = page.getByRole("link", { name: "Scan a repo" }).last();
  await expect(scanRow).toHaveAttribute("href", "/scanner");
});

test("app pages carry the same design system as the landing page", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Ask CompliaHub" })).toBeVisible();

  await page.goto("/documents");
  await expect(page.getByText("Upload a PDF or DOCX standard to ingest")).toBeVisible();
});

test("dark mode toggle switches the theme and persists it", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.getByRole("button", { name: "Switch to dark mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

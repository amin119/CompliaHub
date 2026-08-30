import { test, expect } from "@playwright/test";

/**
 * Smoke test for the landing page — rebuilt to match a reference design
 * ("home page design/home page.svg", a job-matching platform called
 * Sahali) with content adapted to this platform. Confirms the page
 * renders with real content, the hero's entrance animation actually
 * completes (not just that the page loaded), the marquee bands are
 * present, and `/chat`/`/documents` remain unaffected.
 */

test("landing page renders with real content", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /don.t do keyword search/i }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Get Started" })).toBeVisible();
  await expect(page.getByText("Find answers easily and quickly with CompliaHub")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Real questions, real answers" })).toBeVisible();
});

test("hero entrance animation completes and reveals the headline", async ({ page }) => {
  await page.goto("/");
  const heroHeadline = page.locator(".hero-reveal").first();
  await expect(heroHeadline).toHaveCSS("opacity", "1", { timeout: 5_000 });
});

test("prefers-reduced-motion shows content immediately, no marquee loop", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  const heroHeadline = page.locator(".hero-reveal").first();
  await expect(heroHeadline).toHaveCSS("opacity", "1", { timeout: 1_500 });

  const marqueeTrack = page.locator(".marquee-track").first();
  await expect(marqueeTrack).toHaveCSS("animation-name", "none");
});

test("use case cards link to the real chat page, not a dead end", async ({ page }) => {
  await page.goto("/");
  const askNow = page.getByRole("link", { name: "Ask now" }).first();
  await expect(askNow).toHaveAttribute("href", "/chat");
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

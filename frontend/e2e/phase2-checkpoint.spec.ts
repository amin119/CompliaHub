import { test, expect } from "@playwright/test";

const SHOT_DIR = process.env.SHOT_DIR ?? "e2e/__shots__";

test("scanner is discoverable from the landing page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Scan", exact: true }).first()).toHaveAttribute(
    "href",
    "/scanner",
  );
  await expect(page.locator("#how-it-works")).toBeVisible();
  await expect(page.getByRole("link", { name: "Scan a repo" }).first()).toHaveAttribute(
    "href",
    "/scanner",
  );
});

test("hero sequence completes within 1.2s of starting", async ({ page }) => {
  await page.goto("/");

  // Measured from the moment the timeline is actually running (something is
  // still mid-flight) to the moment everything has settled — otherwise the
  // number is dominated by navigation and hydration, not by the animation.
  const elapsed = await page.evaluate(async () => {
    // Scoped to the hero: the other MarkSweeps on the page are scroll-
    // triggered and are legitimately un-swept while sitting at the top.
    const hero = document.querySelector("h1")!.closest("section")!;
    const settled = () =>
      [...hero.querySelectorAll<HTMLElement>(".hero-reveal, .mark-sweep")].every((el) => {
        const style = getComputedStyle(el);
        return el.classList.contains("mark-sweep")
          ? style.clipPath === "inset(0px 0% 0px 0px)"
          : style.opacity === "1";
      });

    const frame = () => new Promise((resolve) => requestAnimationFrame(resolve));

    // Wait for the timeline to actually start; bail out rather than hang if
    // it somehow never does.
    const armedBy = performance.now() + 3_000;
    while (settled() && performance.now() < armedBy) await frame();
    if (settled()) throw new Error("hero timeline never started");

    const start = performance.now();
    while (!settled()) await frame();
    return performance.now() - start;
  });

  console.log(`hero sequence: ${Math.round(elapsed)}ms`);
  expect(elapsed).toBeLessThan(1_200);
});

test("reduced motion renders everything instantly and stops the marquee", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator(".hero-reveal").first()).toHaveCSS("opacity", "1", { timeout: 1_200 });
  await expect(page.locator(".marquee-track").first()).toHaveCSS("animation-name", "none");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("dual final CTA offers both halves", async ({ page }) => {
  await page.goto("/");
  await page.locator("footer").scrollIntoViewIfNeeded();
  const ask = page.getByRole("link", { name: "Ask a question" });
  const scan = page.getByRole("link", { name: "Scan a repo" });
  expect(await ask.count()).toBeGreaterThan(1);
  expect(await scan.count()).toBeGreaterThan(1);
});

for (const theme of ["light", "dark"] as const) {
  test(`landing page screenshots — ${theme}`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.addInitScript((t) => {
      localStorage.setItem("theme", t);
    }, theme);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await page.screenshot({ path: `${SHOT_DIR}/landing-${theme}.png`, fullPage: true });
  });
}

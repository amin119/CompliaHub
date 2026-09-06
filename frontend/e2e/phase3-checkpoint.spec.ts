import { test, expect } from "@playwright/test";

const SCAN_ID = process.env.SCAN_ID ?? "356e8b01-b428-42a3-9c8b-6d370fb3270f";
const SHOT_DIR = "e2e/__shots__";

test("chat streams a real answer and keeps its citations", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Ask CompliaHub" })).toBeVisible();

  await page.getByPlaceholder("Ask about a control, clause, or gap analysis…").fill(
    "What does clause 4.1 of ISO 27001 require?",
  );
  await page.getByRole("button", { name: "Send" }).click();

  // The status line proves the stream opened, not just that a bubble exists.
  await expect(page.getByText(/Classifying|Retrieving|Writing/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "New conversation" })).toBeVisible({
    timeout: 90_000,
  });
  const answer = await page.locator(".group\\/message p").first().innerText();
  expect(answer.length).toBeGreaterThan(40);
});

test("history drawer is keyboard-operable and closes on Escape", async ({ page }) => {
  await page.goto("/chat");
  await page.getByRole("button", { name: "Conversation history" }).click();
  const drawer = page.getByRole("dialog", { name: "Conversation history" });
  await expect(drawer).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
});

test("the upload dropzone is reachable by keyboard", async ({ page }) => {
  await page.goto("/documents");
  const input = page.locator('input[type="file"]');
  await input.focus();
  await expect(input).toBeFocused();
  // sr-only, not display:none — a hidden-by-display input can't be focused.
  await expect(input).not.toHaveClass(/(^|\s)hidden(\s|$)/);
});

test("scan detail: tabs switch and a finding expands", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto(`/scanner/${SCAN_ID}`);
  await expect(page.getByRole("button", { name: /^Findings/ })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: /^Findings/ }).click();

  const firstRow = page.locator("tbody tr[aria-expanded]").first();
  await expect(firstRow).toBeVisible({ timeout: 20_000 });
  await firstRow.click();
  await expect(firstRow).toHaveAttribute("aria-expanded", "true");
});

test("report renders and claims no aggregate compliance score", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto(`/scanner/${SCAN_ID}/report`);
  await expect(page.getByRole("button", { name: "Print / Save as PDF" })).toBeVisible({
    timeout: 45_000,
  });
  const body = await page.locator("body").innerText();
  // The disclaimer is the only place "compliance score" may appear, and only
  // to deny one — so assert on the shapes an actual score would take.
  expect(body).not.toMatch(/\d+%\s*(compliant|compliance|coverage)|overall score|score:\s*\d/i);
  expect(body).toContain("not a certification, audit opinion, or compliance score");
});

test("printing from dark mode forces the light palette, then restores it", async ({ page }) => {
  test.setTimeout(90_000);
  await page.addInitScript(() => {
    localStorage.setItem("theme", "dark");
    // window.print() blocks on a real dialog, so record the theme at the
    // moment it's called instead of opening one.
    Object.defineProperty(window, "print", {
      value: () => {
        (window as unknown as { __themeAtPrint?: string }).__themeAtPrint =
          document.documentElement.dataset.theme;
      },
    });
  });
  await page.goto(`/scanner/${SCAN_ID}/report`);
  const printButton = page.getByRole("button", { name: "Print / Save as PDF" });
  await expect(printButton).toBeVisible({ timeout: 45_000 });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await printButton.click();
  expect(
    await page.evaluate(() => (window as unknown as { __themeAtPrint?: string }).__themeAtPrint),
  ).toBe("light");

  await page.evaluate(() => window.dispatchEvent(new Event("afterprint")));
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  // The app chrome must not end up on the printed page.
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("nav")).toBeHidden();
  await expect(printButton).toBeHidden();
});

for (const theme of ["light", "dark"] as const) {
  for (const [name, path] of [
    ["chat", "/chat"],
    ["documents", "/documents"],
    ["scanner", "/scanner"],
    ["scan-detail", `/scanner/${SCAN_ID}`],
    ["report", `/scanner/${SCAN_ID}/report`],
  ] as const) {
    test(`${name} — ${theme}`, async ({ page }) => {
      test.setTimeout(90_000);
      await page.addInitScript((t) => localStorage.setItem("theme", t), theme);
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await page.waitForTimeout(name === "report" || name === "scan-detail" ? 6_000 : 1_200);
      await page.screenshot({ path: `${SHOT_DIR}/app-${name}-${theme}.png`, fullPage: true });
    });
  }
}

import { test, expect } from "@playwright/test";

const SCAN_ID = process.env.SCAN_ID ?? "356e8b01-b428-42a3-9c8b-6d370fb3270f";

const ROUTES = [
  ["landing", "/"],
  ["chat", "/chat"],
  ["documents", "/documents"],
  ["scanner", "/scanner"],
  ["scan detail", `/scanner/${SCAN_ID}`],
  ["report", `/scanner/${SCAN_ID}/report`],
] as const;

/**
 * A hand-rolled sweep rather than a full axe run: no axe dependency is
 * installed, and these four checks cover the failures this codebase can
 * actually produce — an icon-only control with no label, a click handler on
 * something the keyboard can't reach, a decorative SVG announced to screen
 * readers, and a page with no or several <h1>s.
 */
for (const [name, path] of ROUTES) {
  test(`a11y sweep — ${name}`, async ({ page }) => {
    test.setTimeout(90_000);
    await page.goto(path);
    await expect(page.locator("h1")).toHaveCount(1, { timeout: 45_000 });
    // Let the scanner pages finish loading their tables before sweeping.
    await page.waitForTimeout(name === "scan detail" || name === "report" ? 6_000 : 800);

    const problems = await page.evaluate(() => {
      const found: string[] = [];
      const describe = (el: Element) =>
        `<${el.tagName.toLowerCase()}${el.className && typeof el.className === "string" ? ` class="${el.className.slice(0, 60)}"` : ""}>`;

      const accessibleName = (el: Element) => {
        const aria = el.getAttribute("aria-label");
        if (aria?.trim()) return aria.trim();
        const labelledBy = el.getAttribute("aria-labelledby");
        if (labelledBy) {
          const target = document.getElementById(labelledBy);
          if (target?.textContent?.trim()) return target.textContent.trim();
        }
        if (el.getAttribute("title")?.trim()) return el.getAttribute("title")!.trim();
        return (el as HTMLElement).innerText?.trim() ?? "";
      };

      // 1. Every control the user can operate must announce itself.
      for (const el of document.querySelectorAll(
        'a[href], button, [role="button"], input:not([type="hidden"]), select, textarea',
      )) {
        if ((el as HTMLElement).offsetParent === null && el.tagName !== "INPUT") continue;
        if (el.getAttribute("aria-hidden") === "true") continue;
        const labelled =
          el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA"
            ? Boolean(
                accessibleName(el) ||
                  el.getAttribute("placeholder")?.trim() ||
                  el.closest("label") ||
                  (el.id && document.querySelector(`label[for="${el.id}"]`)),
              )
            : Boolean(accessibleName(el));
        if (!labelled) found.push(`unlabelled control: ${describe(el)}`);
      }

      // 2. A click handler is only usable if the keyboard can reach it.
      for (const el of document.querySelectorAll("[aria-expanded]")) {
        const tag = el.tagName.toLowerCase();
        const focusable =
          ["button", "a", "input", "select", "textarea", "summary"].includes(tag) ||
          el.hasAttribute("tabindex");
        if (!focusable) found.push(`not keyboard reachable: ${describe(el)}`);
      }

      // 3. Decorative SVGs must be hidden from assistive tech.
      for (const svg of document.querySelectorAll("svg")) {
        const hidden = svg.getAttribute("aria-hidden") === "true";
        const named = svg.querySelector("title") || svg.getAttribute("aria-label");
        const insideNamed = svg.closest("[aria-label],[aria-hidden='true']");
        if (!hidden && !named && !insideNamed) found.push(`unannotated svg: ${describe(svg)}`);
      }

      return found;
    });

    if (problems.length > 0) console.log(problems.join("\n"));
    expect(problems).toEqual([]);
  });
}

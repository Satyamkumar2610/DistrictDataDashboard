import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { expect, test } from "@playwright/test";

// The UI overhaul's acceptance checks (docs/design/ui_overhaul.md), so they cannot regress quietly.
const axe = readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");
const ROUTES = ["/", "/atlas", "/district/IND-000202", "/states", "/states/Himachal%20Pradesh", "/crosswalk", "/harmonize", "/research", "/data", "/about"];

test("no route has a serious or critical accessibility violation", async ({ page }) => {
  test.setTimeout(120_000);
  for (const route of ROUTES) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    await page.addScriptTag({ content: axe });
    const found = await page.evaluate(async () => {
      const r = await (window as unknown as { axe: { run: () => Promise<{ violations: { id: string; impact: string; nodes: unknown[] }[] }> } }).axe.run();
      return r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id} (${v.nodes.length})`);
    });
    expect(found, `${route}: ${found.join(", ")}`).toEqual([]);
  }
});

test("no text is smaller than 12px", async ({ page }) => {
  for (const route of ROUTES.filter((r) => r !== "/atlas")) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    const tiny = await page.evaluate(() => [...document.querySelectorAll("body *")]
      .filter((e) => !e.closest(".maplibregl-map, .chart") && [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent!.trim())
        && parseFloat(getComputedStyle(e).fontSize) < 12)
      .map((e) => `${e.tagName}.${e.className}`).slice(0, 5));
    expect(tiny, `${route}: ${tiny.join(", ")}`).toEqual([]);
  }
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("the menu holds every section and a search", async ({ page }) => {
    await page.goto("/research");
    await page.getByRole("button", { name: "Menu" }).click();
    const menu = page.getByRole("dialog", { name: "Menu" });
    for (const name of ["Overview", "Atlas", "States", "Crosswalk", "Harmonize", "Data & quality", "How it works", "Open questions"])
      await expect(menu.getByRole("link", { name, exact: true })).toBeVisible();
    await menu.getByLabel("Find a district (menu)").fill("Malabar");
    await page.getByRole("option", { name: /Malabar/ }).click();
    await expect(page).toHaveURL(/\/district\/IND-000148/);
    await expect(page.getByRole("dialog", { name: "Menu" })).toHaveCount(0);
  });

  test("the atlas keeps most of the screen for the map", async ({ page }) => {
    await page.goto("/atlas");
    await expect(page.getByTestId("atlas-map")).toHaveAttribute("data-ready", "true");
    const map = (await page.getByTestId("atlas-map").boundingBox())!;
    expect(map.height / 844).toBeGreaterThan(0.6);
    await page.getByRole("button", { name: "Colours and compare" }).click();
    await expect(page.getByRole("button", { name: "Area change vs previous map" })).toBeVisible();
  });
});

test("a district page has a section bar that follows the reader", async ({ page }) => {
  await page.goto("/district/IND-000148");
  const bar = page.getByRole("navigation", { name: "On this page" });
  await bar.getByRole("link", { name: "Family tree" }).click();
  await expect(page).toHaveURL(/#family$/);
  await expect(bar.getByRole("link", { name: "Family tree" })).toHaveAttribute("aria-current", "location");
});

test("row hashes stay out of the visible text", async ({ page }) => {
  for (const route of ["/district/IND-000202", "/states/Himachal%20Pradesh"]) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    const text = await page.locator("main").innerText();
    expect(text, route).not.toMatch(/\b[0-9a-f]{32}\b/);
  }
});

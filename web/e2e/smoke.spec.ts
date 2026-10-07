import { expect, test } from "@playwright/test";

const shots = "test-results/screens";

test("overview shows the release figures and charts", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "India's districts, 1951–2025" })).toBeVisible();
  await expect(page.getByText("district identities")).toBeVisible();
  await expect(page.getByTestId("chart-maps").locator("svg")).toBeVisible();
  await page.screenshot({ path: `${shots}/overview.png`, fullPage: true });
});

test("atlas draws the map, switches years and selects a district", async ({ page }) => {
  await page.goto("/atlas");
  await expect(page.getByTestId("atlas-map")).toHaveAttribute("data-ready", "true");
  await page.getByRole("button", { name: "1951" }).click();
  await page.getByLabel("Search districts").fill("Kangra");
  await page.getByRole("option", { name: /Kangra/ }).first().click();
  await expect(page.getByTestId("atlas-selection")).toContainText("IND-000202");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${shots}/atlas.png` });
});

test("district page draws the carved-out land with exact figures", async ({ page }) => {
  await page.goto("/district/IND-000202");
  await expect(page.getByRole("heading", { name: /Kangra/ })).toBeVisible();
  await page.getByRole("group", { name: "Map" }).getByRole("button", { name: "1961" }).click();
  await expect(page.getByTestId("changes")).toContainText("Lahul & Spiti");
  await expect(page.getByTestId("changes")).toContainText("district_relationship");
  await expect(page.getByTestId("sankey").locator("svg")).toBeVisible();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${shots}/district.png`, fullPage: true });
});

test("crosswalk restates a 1951 district on 2025 districts", async ({ page }) => {
  await page.goto("/crosswalk");
  await page.getByLabel("Search districts").fill("Kangra");
  await page.getByRole("option", { name: /Kangra/ }).first().click();
  await expect(page.getByTestId("crosswalk-chart").locator("svg")).toBeVisible();
  await expect(page.getByText("Lahul & Spiti").first()).toBeVisible();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${shots}/crosswalk.png`, fullPage: true });
});

test("research queue and data pages load", async ({ page }) => {
  await page.goto("/research");
  await expect(page.getByTestId("research-table")).toContainText("Firozabad");
  await page.goto("/data");
  await expect(page.getByTestId("gate")).toContainText("PASS");
  await expect(page.getByTestId("dictionary")).toContainText("canonical_key");
  await expect(page.getByTestId("release")).toContainText("ck_registry");
  await expect(page.getByTestId("release")).toContainText("4,605");
  await expect(page.locator("header .version")).toHaveText(/^v\d+\.\d+\.\d+$/);
  await page.screenshot({ path: `${shots}/data.png`, fullPage: true });
});

test("atlas state is a shareable link, and plays through the maps", async ({ page }) => {
  await page.goto("/atlas?year=1981&mode=change&ck=IND-000202");
  await expect(page.getByTestId("atlas-selection")).toContainText("Kangra");
  await expect(page.getByRole("group", { name: "Map year" }).getByRole("button", { name: "1981" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Area change vs previous map" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Play through the maps" }).click();
  await expect(page).toHaveURL(/year=1991/, { timeout: 5000 });
  await page.getByRole("button", { name: "Stop" }).click();
});

test("clicking a map year on the overview opens the atlas there", async ({ page }) => {
  await page.goto("/");
  const chart = page.getByTestId("chart-maps");
  await expect(chart.locator("svg")).toBeVisible();
  await chart.scrollIntoViewIfNeeded();
  const box = (await chart.boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.93, box.y + box.height * 0.5);
  await expect(page).toHaveURL(/\/atlas\?year=2025/);
});

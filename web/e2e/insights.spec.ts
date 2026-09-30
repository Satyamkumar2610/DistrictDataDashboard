import { expect, test } from "@playwright/test";

const shots = "test-results/screens";

test("compare two maps side by side", async ({ page }) => {
  await page.goto("/atlas?year=1981&ck=IND-000202");
  await page.getByRole("button", { name: "Compare two maps" }).click();
  await expect(page.getByTestId("compare")).toBeVisible();
  await expect(page.getByTestId("atlas-map-b")).toHaveAttribute("data-ready", "true");
  await expect(page).toHaveURL(/compare=1/);
  await expect(page.getByRole("group", { name: "Left map year" }).getByRole("button", { name: "1971" })).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${shots}/compare.png` });
});

test("states list and a state's history", async ({ page }) => {
  await page.goto("/states");
  await expect(page.getByTestId("states-table")).toContainText("Telangana");
  await page.getByRole("link", { name: "Himachal Pradesh" }).click();
  await expect(page.getByTestId("state-page")).toContainText("Lahul & Spiti");
  await expect(page.getByTestId("state-page")).toContainText("district_relationship");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${shots}/state.png`, fullPage: true });
});

test("family tree links to relatives", async ({ page }) => {
  await page.goto("/district/IND-000148");
  await expect(page.getByTestId("genealogy").locator("svg")).toBeVisible();
  await expect(page.getByTestId("genealogy")).toContainText("Kozhikode");
  await page.waitForTimeout(800);
  await page.getByTestId("genealogy").screenshot({ path: `${shots}/genealogy.png` });
});

test("release tables download as CSV", async ({ page, request }) => {
  await page.goto("/data");
  await expect(page.getByRole("link", { name: "CSV" }).first()).toBeVisible();
  const res = await request.get("/api/download/crosswalk_to_reference.csv");
  expect(res.status()).toBe(200);
  expect((await res.text()).split("\n")[0]).toContain("share_of_source");
});

test("evidence page compares Wikidata with the maps", async ({ page }) => {
  await page.goto("/evidence");
  await expect(page.getByTestId("evidence-scatter").locator("svg")).toBeVisible();
  await expect(page.getByTestId("evidence-claims")).toContainText("DIFFERS_OVER_10PCT");
  await page.getByLabel("Reason").selectOption("NAME_DIFFERS_FROM_LOCATED_DISTRICT");
  await expect(page).toHaveURL(/reason=NAME_DIFFERS_FROM_LOCATED_DISTRICT/);
  await expect(page.getByTestId("evidence-claims").locator("tbody tr").first()).toBeVisible();
  await page.waitForTimeout(800);
  await page.screenshot({ path: "test-results/screens/evidence.png", fullPage: true });
});

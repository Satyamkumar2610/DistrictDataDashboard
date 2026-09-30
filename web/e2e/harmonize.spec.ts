import { expect, test } from "@playwright/test";

test("harmonize a file of district figures onto the 2025 districts", async ({ page }) => {
  await page.goto("/harmonize");
  const csv = "District,State,Year,Production\nKangra,Himachal Pradesh,1971,1000\nKhangara,Himachal Pradesh,1971,5\nMandi,Himachal Pradesh,1971,400\n";
  await page.getByTestId("harmonize-file").setInputFiles({ name: "hp.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await expect(page.getByLabel("Value", { exact: true })).toHaveValue("Production");
  await page.getByRole("button", { name: "Harmonize", exact: true }).click();
  await expect(page.getByTestId("harmonize-summary")).toContainText("2 of 3 rows matched");
  await expect(page.getByTestId("harmonize-table")).toContainText("Hamirpur");
  await expect(page.getByTestId("harmonize-problems")).toContainText("Khangara");
  await expect(page.getByTestId("harmonize-map")).toHaveAttribute("data-ready", "true");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: "test-results/screens/harmonize.png", fullPage: true });
});

test("the example restates the 1991 map's areas", async ({ page }) => {
  await page.goto("/harmonize");
  await page.getByRole("button", { name: "Use an example" }).click();
  await page.getByRole("button", { name: "Harmonize", exact: true }).click();
  await expect(page.getByTestId("harmonize-summary")).toContainText("rows matched a district identity");
  await expect(page.getByTestId("harmonize-problems")).toHaveCount(0);
});

test("a rate is explained, not allocated", async ({ page }) => {
  await page.goto("/harmonize");
  const csv = "district,state,year,yield\nKangra,Himachal Pradesh,1991,2.1\n";
  await page.getByTestId("harmonize-file").setInputFiles({ name: "y.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: /A rate/ }).click();
  await expect(page.getByText("cannot be shared out by area").first()).toBeVisible();
  await page.getByRole("button", { name: "Harmonize", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("numerator and denominator");
});

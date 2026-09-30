import { expect, test } from "@playwright/test";

test("dark theme re-colours pages, map and charts", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/district/IND-000202");
  await page.getByRole("group", { name: "Map" }).getByRole("button", { name: "1981" }).click();
  await expect(page.getByTestId("changes")).toContainText("Hamirpur");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/screens/district-dark.png" });
  await page.getByRole("button", { name: "Switch light or dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

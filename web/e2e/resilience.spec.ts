import { expect, test } from "@playwright/test";

// What a visitor sees when the data service fails: one banner with one retry, never a page that waits forever.

test("an unreachable data service shows a banner, and retry recovers", async ({ page }) => {
  let fail = true;
  await page.route("**/api/states", (route) => (fail ? route.abort("connectionrefused") : route.fallback()));
  await page.goto("/states");
  const banner = page.getByRole("alert").filter({ hasText: "The data service is not responding" });
  await expect(banner).toBeVisible();
  fail = false;
  await banner.getByRole("button", { name: "Try again" }).click();
  await expect(banner).toBeHidden();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("a missing district is an answer, not an outage", async ({ page }) => {
  await page.goto("/district/IND-999999");
  await expect(page.getByRole("heading", { name: /No district identity/ })).toBeVisible();
  await expect(page.getByText("The data service is not responding")).toHaveCount(0);
});

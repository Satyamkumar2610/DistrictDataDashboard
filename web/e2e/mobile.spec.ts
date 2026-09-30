import { expect, test } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 } });

test("pages fit a phone screen without sideways scrolling", async ({ page }) => {
  for (const path of ["/", "/atlas", "/district/IND-000202", "/crosswalk", "/research", "/data"]) {
    await page.goto(path);
    await page.waitForTimeout(800);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${path} scrolls sideways by ${overflow}px`).toBeLessThanOrEqual(1);
  }
  await page.goto("/district/IND-000202");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/screens/district-mobile.png", fullPage: false });
});

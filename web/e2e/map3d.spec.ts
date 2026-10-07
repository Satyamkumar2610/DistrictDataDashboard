import { expect, test } from "@playwright/test";

// The home page's 3D map draws the release's own districts: on every map, the number of shapes and the number raised
// as new must equal the counts /api/overview reports for that map (the same counts the "Districts on each map" chart shows).
test.use({ reducedMotion: "reduce" });

test("the 3D map shows every district of each map and raises exactly the new ones", async ({ page, request }) => {
  const overview = await (await request.get("/api/overview")).json();
  const maps: { year: number; districts: number; new_identities: number }[] = (overview.data ?? overview).maps;
  await page.goto("/");
  const map = page.getByTestId("map3d");
  const years = page.getByRole("group", { name: "3D map year" });
  for (const m of maps) {
    await years.getByRole("button", { name: String(m.year), exact: true }).click();
    await expect(map).toHaveAttribute("data-year", String(m.year));
    await expect(map).toHaveAttribute("data-count", String(m.districts));
    await expect(map).toHaveAttribute("data-new", String(m.new_identities));
    await expect(map.locator("figcaption")).toContainText(`${m.districts.toLocaleString("en-IN")} districts`);
  }
});

test("reduced motion: the 3D map does not play by itself, and a district on it opens its page", async ({ page }) => {
  await page.goto("/");
  const map = page.getByTestId("map3d");
  await expect(map).toHaveAttribute("data-count", "316");
  await page.waitForTimeout(3500); // longer than one autoplay step
  await expect(map).toHaveAttribute("data-year", "1951");
  await expect(page.getByRole("button", { name: "Play through the maps" })).toHaveAttribute("aria-pressed", "false");
  const box = (await map.locator("canvas").boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); // central India
  await expect(map.locator(".tooltip")).toContainText("km²");
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(page).toHaveURL(/\/district\/IND-\d{6}$/);
});

import { expect, test } from "@playwright/test";

// The usability pass: every explanation on these pages is built from release data, so these assertions use
// values verified against the warehouse (Kangra IND-000202, Malabar IND-000148, Pune IND-000060).

test("the overview's example districts all open real district pages", async ({ page }) => {
  await page.goto("/");
  for (const [name, heading] of [["Kangra", /Kangra/], ["Malabar", /Malabar/], ["Poona", /Pune/], ["Gurgaon", /Gurugram/]] as const) {
    await page.goto("/");
    await page.getByRole("link", { name: new RegExp(`^${name}`) }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading);
  }
});

test("a district's history is told map by map from its own rows", async ({ page }) => {
  await page.goto("/district/IND-000202");
  const story = page.getByTestId("chronology");
  await expect(story).toContainText("11,637 km² (47% of its land) went to Lahul & Spiti");
  await expect(story).toContainText("records a split of Kangra in 1960");
  await expect(story).toContainText("1,169 km² transferred to Una");
  // it opens on the first map where something happened, not on an empty final window
  await expect(page.getByRole("group", { name: "Map" }).getByRole("button", { name: "1961" })).toHaveAttribute("aria-pressed", "true");
  // the self-check is not presented as a statistic
  await expect(page.getByText("mapped_area_km2")).toHaveCount(0);
});

test("small shares are not rounded away, and a one-map district gets a sentence, not a lone dot", async ({ page }) => {
  await page.goto("/district/IND-000148");
  await expect(page.getByTestId("chronology")).toContainText("Mahe: 7 km², <0.1% of its land");
  await expect(page.getByText("on the 1951 map, the only map it is on")).toBeVisible();
});

test("glossary terms explain themselves on focus", async ({ page }) => {
  await page.goto("/");
  // wait for the figures: before they load, the first "measured" on the page is inside a collapsed note
  await expect(page.locator(".tile").first()).toBeVisible();
  const term = page.locator(".tile .term", { hasText: "measured" });
  await term.focus();
  await expect(term.getByRole("tooltip")).toBeVisible();
  await expect(term.getByRole("tooltip")).toContainText("only recorded event");
});

test("the atlas explains an empty comparison instead of showing a silent grey map", async ({ page }) => {
  await page.goto("/atlas?year=1951&mode=change");
  await expect(page.getByRole("status")).toContainText("1951 is the first map");
  await page.getByRole("button", { name: "Show 1961 instead" }).click();
  await expect(page).toHaveURL(/year=1961/);
  await expect(page.getByRole("status")).toHaveCount(0);
});

test("how it works quotes the method and the live release figures", async ({ page }) => {
  await page.goto("/about");
  const about = page.getByTestId("about-page");
  await expect(about).toContainText("at least 90% of its land");
  await expect(about).toContainText("785 district identities");
  await expect(about).toContainText("399 of 609 events are measured exactly");
});

test("the header search opens any district from any page", async ({ page }) => {
  await page.goto("/data");
  await page.getByLabel("Find a district").fill("Poona");
  await page.getByRole("option", { name: /Pune/ }).click();
  await expect(page).toHaveURL(/\/district\/IND-000060/);
});

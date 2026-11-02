import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// One look per style (#1139): a video on one of a style's lanes shows the lane by its name, never its raw id. A video made from a
// published script keeps the script's style (#1189), so it shows as a locked line, not a picker. On the stand-ins; nothing paid.
test("at 390, a video on a Paper lane (paper-flat) is locked to the script's style and switches lane among that style's own", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  const s = await (await page.request.post("/api/scripts", { data: { brand_id: fomo, title: `Lane ${Date.now()}`, description: "", notes: "", reference_replace: "", text: "SCENE 1 — INT. KITCHEN — DAY\nNATE: The dip is in." } })).json();
  // The style is chosen on the script and its video keeps it (#1189): Paper, so a Paper lane may follow.
  expect((await page.request.patch(`/api/scripts/${s.id}`, { data: { look: "paper" } })).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/publish`)).ok()).toBe(true);
  const pid = (await (await page.request.post(`/api/scripts/${s.id}/drafts/0/produce`)).json()).project_id;
  const looks = (await (await page.request.get("/api/looks")).json()) as { id: string; lanes: { id: string; name: string }[] }[];
  const lane = looks.find((l) => l.id === "paper")!.lanes.find((x) => x.id === "paper-flat")!;
  const short = lane.name.replace("Paper · ", "");

  await page.goto(`/b/${fomo}/videos/${pid}?step=plan`);
  await page.getByRole("button", { name: /^Settings: / }).click();
  const sheet = page.getByRole("dialog", { name: "Video settings" });
  // The video keeps its script's style (Reed's walk item 7): a locked line, no Look picker; only Paper's own lanes are offered.
  await expect(sheet.getByText("Style: Paper · set on the script")).toBeVisible();
  await expect(sheet.getByRole("button", { name: /^Look:/ })).toHaveCount(0);
  await sheet.getByRole("button", { name: /^Lane: None/ }).click();
  const lanes = page.getByRole("dialog", { name: "Lane" });
  await expect(lanes.getByText("House")).toHaveCount(0);
  await lanes.getByRole("button", { name: new RegExp(short) }).click();
  await page.getByRole("button", { name: "Switch" }).click();
  await expect(page.getByRole("button", { name: /^Settings: / })).toContainText(short);
  expect(await page.locator("body").textContent()).not.toContain("paper-flat");
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});

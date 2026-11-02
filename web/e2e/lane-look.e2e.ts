import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// One look per style (#1139): a video on one of a style's lanes shows the lane by its name, never its raw id, and the look
// picker offers the styles only, with the lane's style In use. On the stand-ins; nothing paid.
test("at 390, a video on a Paper lane (paper-flat) shows the lane's name in its settings; the picker lists styles, Paper In use", async ({ page }) => {
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
  const switched = await page.request.post(`/api/projects/${pid}/settings`, { data: { look: lane.id } });
  expect(switched.ok(), await switched.text()).toBe(true);

  await page.goto(`/b/${fomo}/videos/${pid}?step=plan`);
  const summary = page.getByRole("button", { name: /^Settings: / });
  await expect(summary).toContainText(lane.name);
  await summary.click();
  const sheet = page.getByRole("dialog", { name: "Video settings" });
  await sheet.getByRole("button", { name: new RegExp(`Look: ${lane.name}`) }).click();
  const paper = page.getByRole("heading", { name: "Paper", exact: true }).locator("xpath=ancestor::li[1]");
  await expect(paper.getByText("In use")).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Paper · / })).toHaveCount(0); // lanes aren't offered as looks
  expect(await page.locator("body").textContent()).not.toContain("paper-flat");
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});

import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// M30 (ux-audit §8.3, Reed's condition on the four steps): every earlier take stays reachable on its clip card. On the
// stand-ins: the director builds a video, one more take is made on the first clip, and the earlier one is played, used
// (with Undo) and downloadable from Other takes. Nothing paid is called.
test("at 390, an earlier take is under Other takes with its reason: Play, Use this take with Undo, Download", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  const text = ["SCENE 1 — INT. KITCHEN — DAY", "NATE: The dip is in. I'm buying.", "NATE: Download fomo through the link in my bio."].join("\n");
  const s = await (await page.request.post("/api/scripts", { data: { brand_id: fomo, title: `Other takes ${Date.now()}`, description: "", notes: "", reference_replace: "", text } })).json();
  expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/publish`)).ok()).toBe(true);
  const pid = (await (await page.request.post(`/api/scripts/${s.id}/drafts/0/produce`)).json()).project_id;

  // The director makes every clip's take; then one more take on the first clip.
  expect((await page.request.post(`/api/projects/${pid}/director`)).ok()).toBe(true);
  await expect.poll(async () => (await (await page.request.get(`/api/projects/${pid}/director`)).json()).status, { timeout: 180_000 }).toBe("delivered");
  const clips = (await (await page.request.get(`/api/projects/${pid}/clips`)).json()) as { id: number; clip_id: string }[];
  const first = clips[0];
  expect((await page.request.post(`/api/projects/${pid}/clips/${first.id}/generate`, { data: { note: "Brighter, please." } })).ok()).toBe(true);
  await expect.poll(async () => ((await (await page.request.get(`/api/projects/${pid}/clips`)).json()) as { takes: unknown[] }[])[0].takes.length, { timeout: 60_000 }).toBe(2);

  const picked = async () => ((await (await page.request.get(`/api/projects/${pid}/clips`)).json()) as { picked_take_id: number }[])[0].picked_take_id;
  const before = await picked();
  await page.goto(`/b/${fomo}/videos/${pid}?step=clips`);
  const card = page.getByRole("listitem", { name: `Clip ${first.clip_id}`, exact: true }).or(page.getByLabel(`Clip ${first.clip_id}`, { exact: true })).first();
  await card.getByText(/^Other takes \(\d+\)$/).click();
  const list = card.getByRole("list", { name: `Other takes for clip ${first.clip_id}` });
  const earlier = list.getByRole("listitem").first();
  await expect(earlier).toContainText(/Take \d+ · (AI: .+|Marked fine: .+|Not checked)/);
  await earlier.getByRole("button", { name: /^Play take \d+$/ }).click();
  await expect(earlier.locator("video")).toBeVisible();
  await expect(earlier.getByRole("link", { name: /^Download take \d+$/ })).toHaveAttribute("download", /-take\d+\.mp4$/);
  await earlier.getByRole("button", { name: /^Use take \d+$/ }).click();
  await expect(page.getByText(/^Take \d+ is picked\.$/)).toBeVisible(); // picking another take needs approving again, unless it checked clean
  await expect.poll(picked).not.toBe(before);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect.poll(picked).toBe(before);
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});

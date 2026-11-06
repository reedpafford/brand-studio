import { expect, test } from "@playwright/test";
import { approveCastWhenReady, makeIt, onBrand, signIn } from "./helpers";

// v6 screen 8 (S6-02, S6-03) on the stand-ins: after a delivered run, the owner opens a clip on the Clips tab, presses
// Another take, and the new take lands beside the one in the cut; Use this take puts it in Cut 2. Nothing paid is called.
test("on the Clips tab, Another take makes a new take of the clip on the stand-ins", async ({ page }) => {
  test.setTimeout(240_000);
  await signIn(page, "reed@example.com");
  approveCastWhenReady(page); // the Cast tab's Approve cast & places (#1324)
  await onBrand(page, "fomo");
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  const text = ["SCENE 1 — INT. KITCHEN — DAY", "NATE: The dip is in. I'm buying.", "NATE: Download fomo through the link in my bio."].join("\n");
  const s = await (await page.request.post("/api/scripts", { data: { brand_id: fomo, title: `Takes ${Date.now()}`, description: "", notes: "", reference_replace: "", text } })).json();
  expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/publish`)).ok()).toBe(true);
  const made = await page.request.post(`/api/scripts/${s.id}/drafts/0/produce`);
  expect(made.ok()).toBe(true);
  const pid = (await made.json()).project_id;

  await page.goto(`/b/${fomo}/videos/${pid}`);
  await page.getByRole("button", { name: /^Make it/ }).click();
  await makeIt(page, pid);
  await expect(page.getByRole("banner").getByText(/^Delivered$/)).toBeVisible({ timeout: 200_000 });

  await page.getByRole("tab", { name: "Clips" }).click();
  await page.getByRole("button", { name: "Open clip 1" }).click();
  const clip = page.getByRole("region", { name: "Clip 1" });
  await expect(clip.getByText(/^Take \d+ · in the cut$/)).toBeVisible();
  const takes = clip.locator('video[aria-label^="Take "]');
  const before = await takes.count();
  await clip.getByRole("button", { name: /^Another take · up to \$\d/ }).first().click();
  await expect(takes).toHaveCount(before + 1, { timeout: 60_000 });
  await expect(clip.getByLabel(`Take ${before + 1}`, { exact: true })).toBeVisible(); // made, beside the one in the cut

  // Use this take · free: it goes in the cut, and the cut is made again by itself (S7-05): Cut 2, once it's ready.
  await clip.getByRole("button", { name: "Use this take · free" }).last().click();
  await expect(clip.getByText(`Take ${before + 1} · in the cut`)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("tab", { name: "Cut" }).click();
  await expect(page.getByRole("radiogroup", { name: "Which cut" }).getByRole("radio", { name: "Cut 2" })).toHaveAttribute("aria-checked", "true", { timeout: 60_000 });
});

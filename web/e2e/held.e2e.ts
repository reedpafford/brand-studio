import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// QA on #1088 (with #1099): an editor's song takes on a script read Send for approval, wait on that script, and Withdraw
// takes them back for nothing. (An editor's New video send waiting for the owner is in freestyle.e2e.ts; Quick clip is gone.)
test("at 390, an editor's song takes on a script are sent for approval and wait on that script", async ({ page, browser, baseURL }) => {
  test.setTimeout(120_000);
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const inv = await (await page.request.post("/api/team/invites", { data: { email: `held-song-${Date.now()}@example.com` } })).json();
  const ed = await (await browser.newContext({ baseURL, viewport: { width: 390, height: 900 } })).newPage();
  expect((await ed.request.post("/api/auth/accept-invite", { data: { token: inv.token, name: "Sol", password: "correct horse battery staple" } })).ok()).toBe(true);
  const brands = (await (await ed.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  await ed.goto(`/b/${fomo}/scripts`);
  await ed.getByRole("button", { name: "New script" }).click();
  await ed.getByRole("menuitem", { name: /Song/ }).click();
  await ed.getByLabel("Lyrics").fill("[Verse]\nThe dip is in, I'm buying\n[Chorus]\nfomo, link in my bio");
  await ed.getByLabel("Music style").fill("pop, upbeat");
  await ed.getByRole("button", { name: "Save lyrics" }).click();
  await ed.getByRole("button", { name: /Next: Takes/ }).click();
  await ed.getByRole("button", { name: /^Send for approval · \d+ credits?/ }).click();
  await expect(ed.getByText("Sent for approval. It waits for the owner's OK; nothing is charged until then.")).toBeVisible();
  await expect(ed.getByText("Waiting for approval")).toBeVisible();
  await expect(ed.getByText(/Your song or music · .*Songs, narration and music on a script wait for the owner's OK\./)).toBeVisible();
  await ed.getByRole("button", { name: "Withdraw" }).click();
  await expect(ed.getByText("Withdrawn. Nothing was charged.")).toBeVisible();
  const sizes = await ed.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});

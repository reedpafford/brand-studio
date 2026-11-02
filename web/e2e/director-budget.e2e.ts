import { expect, test } from "@playwright/test";
import { onBrand, runToEnd, signIn } from "./helpers";

// DECISIONS #1066 (with #1143): the director's own turns never count toward the video's budget. After one normal run the
// steps' cost bar is not over budget for that, and says the director's time apart, in credits.
test("at 390, after one director run the cost bar leaves the director's time out of the budget and says it apart", async ({ page, browser, baseURL }) => {
  test.setTimeout(240_000);
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  const text = ["SCENE 1 — INT. KITCHEN — DAY", "NATE: The dip is in. I'm buying.", "NATE: Download fomo through the link in my bio."].join("\n");
  const s = await (await page.request.post("/api/scripts", { data: { brand_id: fomo, title: `Budget ${Date.now()}`, description: "", notes: "", reference_replace: "", text } })).json();
  expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/publish`)).ok()).toBe(true);
  const inv = await (await page.request.post("/api/team/invites", { data: { email: `budget-${Date.now()}@example.com` } })).json();
  const ed = await (await browser.newContext({ baseURL, viewport: { width: 390, height: 900 } })).newPage();
  expect((await ed.request.post("/api/auth/accept-invite", { data: { token: inv.token, name: "Bea", password: "correct horse battery staple" } })).ok()).toBe(true);
  const pid = (await (await ed.request.post(`/api/scripts/${s.id}/drafts/0/produce`)).json()).project_id;
  expect((await ed.request.post(`/api/projects/${pid}/director`)).ok()).toBe(true);
  await runToEnd(page, pid); // past the director's own limit it waits for the owner's OK
  await expect.poll(async () => (await (await ed.request.get(`/api/projects/${pid}/director`)).json()).status, { timeout: 200_000 }).toBe("delivered");
  const p = (await (await ed.request.get(`/api/projects/${pid}`)).json()) as { credits_used: number; budget_credits: number; director_credits: number };
  expect(p.director_credits).toBeGreaterThan(0);
  expect(p.credits_used - p.director_credits).toBeLessThanOrEqual(p.budget_credits);

  await ed.goto(`/b/${fomo}/videos/${pid}?step=clips`);
  const bar = ed.getByRole("region", { name: "Cost" });
  await expect(bar).toContainText(/the director's time, \d+(\.\d)? credits?\./);
  await expect(bar).not.toContainText("Over budget");
  expect(await ed.locator("main").textContent()).not.toMatch(/\$\d/); // credits only for an editor
});

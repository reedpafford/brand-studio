import { expect, test, type Page } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";
// Opt-in (E2E_WALK=1, about 6 minutes): an editor at 390 makes a video, start to final cut, from a published script
// that skipped Breakdown, Variations and Cast, for Iron Paws (a bag beat) and fomo, on the free stand-ins.
// Every point where the editor has no one-click way forward is logged ("BLOCK ...") and fails the test.
test.skip(!process.env.E2E_WALK, "the long editor walk runs only with E2E_WALK=1");
test.use({ viewport: { width: 390, height: 844 } });
const IRON = [
  "SCENE 1 — INT. KITCHEN — MORNING",
  "A pitbull sits by the couch, eyes crusty, licking his paws.",
  "PITBULL (V.O.): Crusty eyes every morning. That is my gut breaking down.",
  "PITBULL (V.O.): Paws that never stop getting licked. That is also my gut breaking down.",
  "SCENE 2 — INT. KITCHEN — NIGHT",
  "She mixes the Iron Paws greens powder into his bowl; the bag sits on the counter.",
  "PITBULL (V.O.): Then one night she found something. A greens powder called Iron Paws.",
  "PITBULL (V.O.): You just did not know what the signs meant. But now you do. The link is below.",
].join("\n");
const FOMO = [
  "SCENE 1 — EXT. CLIFFTOP ALTAR — DAY",
  "NATE: I do.",
  "MARA: HELL NO! I'm marrying him!",
  "SCENE 2 — INT. NATE'S BEDROOM — NIGHT",
  "★ fomo screen: Token chart up — fills the frame",
  "NATE: Want to trade like me? Download fomo through the link in my bio.",
].join("\n");
const blocks: string[] = [];
async function state(page: Page, where: string) {
  const s = await page.evaluate(() => {
    const txt = (el: Element | null) => (el?.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 160);
    const alerts = [...document.querySelectorAll('[role="alert"]')].map(txt).filter(Boolean);
    const next = [...document.querySelectorAll("button")].find((b) => /^Next/.test(b.textContent?.trim() ?? "")) as HTMLButtonElement | undefined;
    const reason = (b: HTMLElement) => (b.getAttribute("aria-describedby") ? txt(document.getElementById(b.getAttribute("aria-describedby")!)) : "");
    const off = [...document.querySelectorAll<HTMLButtonElement>("button:disabled")].map((b) => `${txt(b)}${reason(b) ? ` [${reason(b)}]` : ""}`).filter(Boolean);
    const step = txt([...document.querySelectorAll("main button")].find((b) => /^Step \d of/.test(b.textContent ?? "")) ?? null);
    return { step, next: next ? `${txt(next)}${next.disabled ? ` DISABLED [${reason(next)}]` : ""}` : "none", alerts, off: off.slice(0, 8), sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth };
  });
  console.log(`[${where}] ${JSON.stringify(s)}`);
  return s;
}
async function block(page: Page, where: string, why: string) {
  const s = await state(page, where);
  blocks.push(`${where}: ${why} :: next=${s.next} alerts=${JSON.stringify(s.alerts)} off=${JSON.stringify(s.off)}`);
  console.log(`BLOCK ${where}: ${why}`);
  const vid = page.url().match(/(?:videos|projects)\/(\d+)/)?.[1];
  if (vid) {
    const p = await (await page.request.get(`/api/projects/${vid}`)).json();
    console.log("PROJECT", JSON.stringify({ status: p.status, budget: p.budget_credits, used: p.credits_used, est: p.estimate_credits, planned: p.planned_seconds, bd: p.breakdown_seconds }));
    const jobs = (await (await page.request.get(`/api/jobs`)).json()) as { project_id: number; kind: string; status: string; credits: number; step?: string }[];
    console.log("JOBS", JSON.stringify(jobs.filter((j) => String(j.project_id) === vid).map((j) => `${j.kind}/${j.step ?? ""}:${j.status}:${j.credits}`)));
  }
  await page.screenshot({ path: `test-results/walk-${where.replace(/\W+/g, "-")}.png`, fullPage: true });
}
const btn = (page: Page, name: RegExp | string) => page.getByRole("button", { name }).first();
async function clickWhenOn(page: Page, name: RegExp | string, ms: number) {
  const b = btn(page, name);
  try { await expect(b).toBeEnabled({ timeout: ms }); await b.click(); return true; } catch { return false; }
}
async function next(page: Page, label: RegExp, where: string, ms = 60_000) {
  const ok = await clickWhenOn(page, label, ms);
  if (!ok) await block(page, where, `${label} not on after ${ms / 1000}s`);
  await page.waitForTimeout(1500);
  return ok;
}
async function walk(ed: Page, brand: number, title: string, tag: string) {
  ed.setDefaultTimeout(10_000);
  const errors: string[] = [];
  ed.on("pageerror", (e) => errors.push(e.message));
  await ed.goto(`/b/${brand}/scripts`);
  const row = ed.locator("li").filter({ hasText: title }).first();
  await expect(row).toBeVisible({ timeout: 15_000 }).catch(async () => block(ed, `${tag} library`, "script not listed for the editor"));
  console.log(tag, "row:", (await row.innerText()).replace(/\n+/g, " | "));
  await row.getByRole("link", { name: /^Version A, ready to make/ }).click().catch(async () => block(ed, `${tag} library`, "no 'Version A, ready to make' chip"));
  const make = ed.getByRole("button", { name: /^Make this version/ }).first();
  try { await expect(make).toBeEnabled({ timeout: 15_000 }); } catch { await block(ed, `${tag} panel`, "Make this version not on"); return; }
  console.log(tag, "panel:", (await ed.getByRole("dialog").last().innerText().catch(() => "")).replace(/\n+/g, " | ").slice(0, 500));
  await make.click();
  await ed.waitForURL(/\/(videos|projects)\/\d+/, { timeout: 30_000 }).catch(async () => block(ed, `${tag} make`, "didn't open the video"));
  const vid = Number(ed.url().match(/(?:videos|projects)\/(\d+)/)?.[1]);
  console.log(tag, "video", vid, ed.url());
  // Breakdown
  await ed.waitForTimeout(3000);
  await state(ed, `${tag} breakdown`);
  if (await btn(ed, /^Make shots|^Make the breakdown|^Make breakdown/).count()) await clickWhenOn(ed, /^Make shots|^Make the breakdown|^Make breakdown/, 10_000);
  if (!(await next(ed, /^Next: Assets/, `${tag} breakdown`, 90_000))) return;
  // Assets: looks are made by themselves, then approved
  await state(ed, `${tag} assets`);
  for (let i = 0; i < 8; i++) {
    if (await btn(ed, /^Next: Storyboard/).isEnabled().catch(() => false)) break;
    const st = await state(ed, `${tag} assets ${i}`);
    if (/flavour first/.test(st.next)) {
      const flav = ed.getByRole("region", { name: "Products" }).locator('button[aria-pressed="false"]').first();
      console.log(tag, "picking a flavour:", await flav.innerText().catch(() => "none"));
      await flav.click().catch(async () => block(ed, `${tag} assets`, "no flavour button to pick"));
      await ed.waitForTimeout(1500);
      continue;
    }
    if (await btn(ed, /^Approve all$|^Approve \d+$/).isEnabled().catch(() => false)) { await btn(ed, /^Approve all$|^Approve \d+$/).click(); await ed.waitForTimeout(1500); continue; }
    const look = btn(ed, /^Make a look/);
    if (i >= 3 && (await look.isEnabled().catch(() => false))) { await look.click(); }
    await ed.waitForTimeout(8_000);
  }
  if (!(await next(ed, /^Next: Storyboard/, `${tag} assets`, 20_000))) return;
  // Storyboard
  await state(ed, `${tag} storyboard`);
  if (!(await clickWhenOn(ed, /^Make storyboard/, 20_000))) { await block(ed, `${tag} storyboard`, "Make storyboard not on"); return; }
  if (!(await clickWhenOn(ed, /^Approve all$|^Approve \d+$/, 120_000))) await block(ed, `${tag} storyboard`, "no Approve all for stills");
  await ed.waitForTimeout(1500);
  if (!(await next(ed, /^Next: Clips/, `${tag} storyboard`, 30_000))) return;
  // Clips
  await state(ed, `${tag} clips`);
  if (await btn(ed, /^Write clip prompts/).count()) if (!(await clickWhenOn(ed, /^Write clip prompts/, 20_000))) { await block(ed, `${tag} clips`, "Write clip prompts not on"); return; }
  await expect(ed.getByRole("listitem", { name: /^Clip c1$/ })).toBeVisible({ timeout: 60_000 }).catch(async () => block(ed, `${tag} clips`, "no clips listed"));
  await ed.waitForTimeout(2000);
  for (const b of await ed.getByRole("button", { name: /^Prompt for c\d+ looks good$/ }).all()) await b.click().catch(() => {});
  await ed.waitForTimeout(1500);
  await state(ed, `${tag} clips read`);
  if (await btn(ed, /^Make the takes/).count()) { if (!(await clickWhenOn(ed, /^Make the takes/, 20_000))) await block(ed, `${tag} clips`, "Make the takes not on"); }
  else for (const b of await ed.locator("main").getByRole("button", { name: /^Make clip/ }).all()) await b.click().catch(() => {});
  if (!(await clickWhenOn(ed, /^Approve all$|^Approve \d+$/, 180_000))) {
    const each = ed.getByRole("button", { name: "✓ Looks good" });
    if (await each.count()) for (const b of await each.all()) await b.click().catch(() => {});
    else await block(ed, `${tag} clips`, "no way to approve takes");
  }
  await ed.waitForTimeout(2000);
  if (!(await next(ed, /^Next: Downloads/, `${tag} clips`, 60_000))) return;
  // Downloads / final video
  await state(ed, `${tag} downloads`);
  // The whole video is put together by itself once every clip is approved; Make the video is only there when it isn't yet.
  if (await btn(ed, /^Make the video/).isEnabled().catch(() => false)) await btn(ed, /^Make the video/).click();
  await expect(ed.getByRole("link", { name: /Download MP4/ })).toBeVisible({ timeout: 120_000 }).catch(async () => block(ed, `${tag} downloads`, "no final video to download"));
  await state(ed, `${tag} done`);
  console.log(tag, "page errors", JSON.stringify(errors));
  if (errors.length) blocks.push(`${tag}: page errors ${JSON.stringify(errors)}`);
}
test("editor walk: published script with no breakdown, variations or cast, at 390", async ({ page, browser }) => {
  test.setTimeout(1_500_000);
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const id = async (name: string) => brands.find((b) => b.name === name)?.id ?? (await emptyBrand(page, name));
  const iron = await id("Iron Paws"), fomo = await id("fomo");
  console.log("brands", JSON.stringify(brands.map((b) => b.name)), "iron", iron, "fomo", fomo);
  const made: [number, string, string][] = [];
  for (const [brand, title, text] of [[iron, "QA Pitbull walk", IRON], [fomo, "QA fomo walk", FOMO]] as const) {
    const s = await (await page.request.post("/api/scripts", { data: { brand_id: brand, title, description: "QA walk.", notes: "", reference_replace: "", text } })).json();
    console.log(title, "approve", (await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).status());
    const pub = await page.request.post(`/api/scripts/${s.id}/publish`);
    console.log(title, "publish", pub.status(), pub.ok() ? "" : (await pub.text()).slice(0, 200));
    made.push([brand, title, String(s.id)]);
  }
  const inv = await (await page.request.post("/api/team/invites", { data: { email: "qa2-walk@example.com" } })).json();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const ed = await ctx.newPage();
  console.log("accept", (await ed.request.post("/api/auth/accept-invite", { data: { token: inv.token, name: "Walker", password: "correct horse battery staple" } })).status());
  await ed.goto("/");
  await expect(ed.getByRole("button", { name: "Account menu" })).toBeVisible();
  for (const [brand, title] of made.filter(([, t]) => !process.env.E2E_WALK_ONLY || t.includes(process.env.E2E_WALK_ONLY))) await walk(ed, brand, title, title.includes("Pitbull") ? "iron" : "fomo");
  console.log("BLOCKS", blocks.length, JSON.stringify(blocks, null, 1));
  expect(blocks).toEqual([]);
});

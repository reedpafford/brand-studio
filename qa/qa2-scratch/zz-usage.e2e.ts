import { expect, test } from "@playwright/test";
import { PASSWORD, signIn } from "./helpers";
// QA-2 scratch: Usage is Reed's only; 390 audit on /usage and a brand's page; an editor sees Page not found and no $.
const audit = (page: import("@playwright/test").Page) => page.evaluate(() => {
  const small = [...document.querySelectorAll<HTMLElement>("a,button,input:not(.sr-only),select,textarea")]
    .filter((el) => { const box = (el.tagName === "INPUT" && el.closest("label")) ? el.closest("label")!.getBoundingClientRect() : el.getBoundingClientRect(); return box.height > 0 && box.height < 43.5; })
    .map((el) => `${el.tagName}[${Math.round(el.getBoundingClientRect().height)}] ${(el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 30)}`);
  return { sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth, small };
});
test("Reed's Usage pages at 390", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  await page.goto("/usage");
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("heading", { name: /Usage/ }).first()).toBeVisible();
  expect(await audit(page)).toEqual({ sideways: 0, small: [] });
  await page.goto(`/usage/brands/${brands.find((b) => b.name === "fomo")!.id}`);
  await page.waitForLoadState("networkidle");
  expect(await audit(page)).toEqual({ sideways: 0, small: [] });
});
test("an editor gets Page not found on Usage and sees no dollars", async ({ page, browser }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const token = (await (await page.request.post("/api/team/invites", { data: { email: "qa2-usage@example.com" } })).json()).token;
  const ctx = await browser.newContext();
  const ed = await ctx.newPage();
  const r = await ed.request.post("/api/auth/accept-invite", { data: { token, name: "Uma", password: PASSWORD } });
  expect(r.ok()).toBeTruthy();
  const brands = (await (await ed.request.get("/api/brands")).json()) as { id: number }[];
  for (const url of ["/usage", `/usage/brands/${brands[0].id}`]) {
    await ed.goto(url);
    await expect(ed.getByText("Page not found.")).toBeVisible();
    expect(await ed.locator("body").innerText()).not.toMatch(/\$/);
  }
  expect((await ed.request.get("/api/usage/summary")).status()).toBe(404);
  await ed.goto("/");
  await expect(ed.getByRole("link", { name: /Usage/ })).toHaveCount(0);
  await ctx.close();
});

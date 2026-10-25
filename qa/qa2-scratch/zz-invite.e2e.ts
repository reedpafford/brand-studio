import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { PASSWORD, signIn } from "./helpers";

// QA-2 scratch walk of the invite page at phone width (not committed).
test.use({ viewport: { width: 390, height: 844 } });
test.describe.configure({ mode: "serial" });

async function invite(page: Page, email: string): Promise<string> {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const r = await page.request.post("/api/team/invites", { data: { email } });
  expect(r.status()).toBe(201);
  const token = (await r.json()).token as string;
  await page.context().clearCookies();
  return token;
}

async function noSideways(page: Page) {
  const [sw, cw] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  expect(sw).toBeLessThanOrEqual(cw);
}

async function expectInvalid(page: Page, token: string) {
  await page.goto(`/invite/${token}`);
  await expect(page.getByRole("heading", { name: "Invite not valid" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveText("This invite link is not valid any more.");
  await expect(page.getByText("Ask whoever invited you to send a new link.")).toBeVisible();
  await expect(page.getByLabel("Your name")).toHaveCount(0);
  await noSideways(page);
}

let used = "";

test("a valid invite says who, where and as what; then it works once", async ({ page }) => {
  used = await invite(page, "qa2-valid@example.com");
  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));
  await page.goto(`/invite/${used}`);
  await expect(page.getByRole("heading", { name: "Join Studio" })).toBeVisible();
  await expect(page.getByText("Reed invited you to Studio as an editor. Your email is qa2-valid@example.com.")).toBeVisible();
  await noSideways(page);
  await page.screenshot({ path: "test-results/qa2-invite-valid-390.png", fullPage: true });
  const name = page.getByLabel("Your name");
  const box = await page.getByRole("button", { name: "Create my account" }).boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(44);
  await name.fill("Valid Val");
  await page.getByLabel(/Choose a password/).fill(PASSWORD);
  await page.getByRole("button", { name: "Create my account" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  // only the page address carries the token, never an API call's address
  expect(requests.filter((u) => u.includes("/api/") && u.includes(used))).toEqual([]);
});

test("a used invite says it is not valid", async ({ page }) => {
  await expectInvalid(page, used);
});

test("an expired invite says it is not valid", async ({ page }) => {
  const token = await invite(page, "qa2-expired@example.com");
  const db = path.resolve(process.cwd(), "e2e/.data/e2e.db");
  execFileSync("python3", ["-c", "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"update invites set expires_at='2000-01-01 00:00:00.000000' where email=?\", (sys.argv[2],)); c.commit()", db, "qa2-expired@example.com"]);
  await expectInvalid(page, token);
  await page.screenshot({ path: "test-results/qa2-invite-invalid-390.png", fullPage: true });
});

test("a made-up invite says it is not valid", async ({ page }) => {
  await expectInvalid(page, "made-up-token-123");
});

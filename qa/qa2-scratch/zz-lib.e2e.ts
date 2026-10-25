import { expect, test, type Page } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// QA-2 scratch (not committed): a published script can't be renamed or edited; locked steps say Coming soon; 390 audit of the flow.
async function published(page: Page) {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brand = await emptyBrand(page, "Lib QA Co");
  const made = await (await page.request.post("/api/scripts", { data: { brand_id: brand, title: "Locked words", description: "QA", text: "BO: Salmon again?\nMIA: Try it." } })).json();
  expect((await page.request.post(`/api/scripts/${made.id}/drafts/0/approve`)).ok()).toBeTruthy();
  const pub = await page.request.post(`/api/scripts/${made.id}/publish`);
  expect(pub.ok(), await pub.text()).toBeTruthy();
  return `/b/${brand}/scripts/${made.id}`;
}

for (const [w, h] of [[1280, 800], [390, 844]] as const) {
  test(`published script at ${w}: no rename, no edit, steps locked with Coming soon`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    const url = await published(page);
    await page.goto(url);
    await expect(page.getByRole("heading", { name: "Locked words" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Rename" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Edit description" })).toHaveCount(0);
    await page.goto(`${url}?step=script`);
    await expect(page.getByRole("list", { name: "Script text" })).toContainText("MIA: Try it.");
    await expect(page.getByRole("button", { name: "Edit", exact: true })).toHaveCount(0);
    await expect(page.getByLabel("Your script")).toHaveCount(0);
    if (w >= 1024) {
      const directions = page.getByRole("list", { name: "Steps" }).getByRole("button", { name: /Directions/ });
      await expect(directions).toHaveAttribute("aria-disabled", "true");
      const d = await directions.getAttribute("aria-describedby");
      await expect(page.locator(`[id="${d}"]`)).toContainText("Coming soon");
    } else {
      await page.getByRole("button", { name: /^Step \d of 7/ }).click();
      await expect(page.getByRole("dialog", { name: "Steps" }).getByText("Coming soon").first()).toBeVisible();
      await page.keyboard.press("Escape");
      const r = await page.evaluate(() => {
        const de = document.documentElement;
        const small = [...document.querySelectorAll<HTMLElement>("a,button,input:not(.sr-only),select,textarea")]
          .filter((el) => { const b = el.getBoundingClientRect(); return b.height > 0 && b.height < 43.5; })
          .map((el) => `${el.tagName}[${Math.round(el.getBoundingClientRect().height)}] ${(el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 30)}`);
        return { sideways: de.scrollWidth - de.clientWidth, small };
      });
      expect(r).toEqual({ sideways: 0, small: [] });
    }
    // the server refuses edits too
    const id = url.split("/").pop();
    const put = await page.request.put(`/api/scripts/${id}/drafts/0`, { data: { text: "changed" } });
    expect(put.status()).toBe(409);
  });
}

test("New script and the draft writing page at 390: nothing under 44px, no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brand = await emptyBrand(page, "Lib QA Two");
  await page.goto(`/b/${brand}/scripts/new`);
  const audit = () => page.evaluate(() => {
    const de = document.documentElement;
    const small = [...document.querySelectorAll<HTMLElement>("a,button,input:not(.sr-only),select,textarea")]
      .filter((el) => { const b = el.getBoundingClientRect(); return b.height > 0 && b.height < 43.5; })
      .map((el) => `${el.tagName}[${Math.round(el.getBoundingClientRect().height)}] ${(el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 30)}`);
    return { sideways: de.scrollWidth - de.clientWidth, small };
  });
  await expect(page.getByLabel("Title")).toBeVisible();
  expect(await audit()).toEqual({ sideways: 0, small: [] });
  await page.getByLabel("Title").fill("Phone draft");
  await page.getByLabel("What it's for").fill("A quick test.");
  await page.getByRole("button", { name: "Create script" }).click();
  await expect(page.getByRole("heading", { name: "Script", exact: true, level: 2 })).toBeVisible();
  expect(await audit()).toEqual({ sideways: 0, small: [] });
});

test("publishing from the page approves the words first, and the steps are read-only after", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brand = await emptyBrand(page, "Lib QA Three");
  const made = await (await page.request.post("/api/scripts", { data: { brand_id: brand, title: "Pub via page", description: "QA", text: "BO: Hi." } })).json();
  await page.goto(`/b/${brand}/scripts/${made.id}?step=publish`);
  await page.getByRole("button", { name: /^Publish 1 version/ }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByText(/Published\./)).toBeVisible();
  const s = await (await page.request.get(`/api/scripts/${made.id}`)).json();
  expect(s.published).toBe(true);
  expect(s.versions.every((v: { status: string }) => v.status === "approved")).toBe(true);
  for (const step of ["description", "script", "cast"]) {
    await page.goto(`/b/${brand}/scripts/${made.id}?step=${step}`);
    await expect(page.getByRole("button", { name: /^(Edit|Edit description|Rename|Add a role|Lock .* to a look)$/ })).toHaveCount(0);
  }
});

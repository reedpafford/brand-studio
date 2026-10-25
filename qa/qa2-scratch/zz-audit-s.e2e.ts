import { writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// QA-2 scratch audit (not committed): at 390x844, every main page and project stage, after the suite has run.
// Reports sideways scroll and visible controls under 44px tall. Writes test-results/qa2-audit.json.
test.use({ viewport: { width: 390, height: 844 } });

test("phone audit", async ({ page }) => {
  test.setTimeout(240_000);
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  const pipe = brands.find((b) => b.name === "Pipeline Co")?.id ?? fomo;
  const projects = (await (await page.request.get(`/api/projects?brand_id=${pipe}`)).json()) as { id: number; name: string }[];
  const proj = projects.find((p) => p.name === "Pipeline test") ?? projects[0];
  const urls = [
    `/b/${fomo}/scripts`, `/b/${fomo}/projects`, `/b/${fomo}/projects/new`, `/b/${fomo}/kit`, `/b/${fomo}/screens`,
    `/b/${fomo}/library/characters`, `/b/${fomo}/clip`, `/team`, `/approvals`,
    ...(proj ? ["brief", "script", "enhance", "breakdown", "storyboard", "clips"].map((s) => `/b/${pipe}/projects/${proj.id}?stage=${s}`) : []),
  ];
  const report: Record<string, { sideways: number; small: string[] }> = {};
  const passes: [string, string, string | null][] = [];
  for (const url of urls) {
    passes.push([url, url, null]);
    const st = url.match(/stage=(\w+)/)?.[1];
    if (st) passes.push([`${url} (stage pane)`, url, st]);
  }
  for (const [key, url, st] of passes) {
    await page.goto(url);
    await page.waitForLoadState("networkidle");
    if (st) {
      // the phone switcher: the tab that isn't "Script"
      const pane = page.getByRole("tab").filter({ hasNotText: /^Script$/ });
      if (await pane.count()) await pane.first().click();
    }
    await page.waitForTimeout(400);
    report[key] = await page.evaluate(() => {
      const de = document.documentElement;
      const small = new Set<string>();
      for (const el of document.querySelectorAll<HTMLElement>("a,button,input:not([type=hidden]):not(.sr-only),select,textarea,summary,[role=switch],[role=tab]")) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0 || getComputedStyle(el).visibility === "hidden") continue;
        // a checkbox/radio counts by its label's box
        const box = (el instanceof HTMLInputElement && /checkbox|radio/.test(el.type) && el.closest("label")) ? el.closest("label")!.getBoundingClientRect() : r;
        if (box.height < 43.5) small.add(`${el.tagName.toLowerCase()}[${Math.round(box.height)}] ${(el.getAttribute("aria-label") || el.textContent || (el as HTMLInputElement).type || "").trim().replace(/\s+/g, " ").slice(0, 30)}`);
      }
      return { sideways: Math.max(0, de.scrollWidth - de.clientWidth), small: [...small].sort() };
    });
  }
  writeFileSync("test-results/qa2-audit.json", JSON.stringify(report, null, 1));
});

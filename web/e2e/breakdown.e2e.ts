import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

test("Make breakdown is refused while generation is switched off, and nothing is queued", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Script Shop");
  const made = await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Breakdown test", planned_seconds: 20 } });
  const id = (await made.json()).id;
  await page.request.put(`/api/projects/${id}/script`, { data: { text: "MAX: Hello." } });
  await page.goto(`/b/${brandId}/projects/${id}?stage=breakdown`);
  await page.getByRole("button", { name: /Make breakdown/ }).click();
  await expect(page.getByRole("alert")).toContainText("Generation is switched off");
  const jobs = await (await page.request.get("/api/jobs")).json();
  expect(jobs.filter((j: { project_id: number }) => j.project_id === id)).toHaveLength(0);
});

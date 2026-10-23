import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

const shot = (id: string, lines: number[], speaker: string, line: string, seconds: number) => ({
  id,
  script_lines: lines,
  speaker,
  line,
  action: "They argue.",
  reaction: null,
  camera: "Close-up, push in",
  seconds,
  character_ids: [],
  place_id: null,
  moment: null,
  screen_ids: [],
});

test("Make storyboard is refused while generation is switched off, and nothing is queued", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Script Shop");
  const made = await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Storyboard test", planned_seconds: 20 } });
  const id = (await made.json()).id;
  await page.request.put(`/api/projects/${id}/script`, { data: { text: "SCENE 1 - KITCHEN\nMOM: Where is it?\nNATE: Gone." } });
  const breakdown = {
    hook: "Mom asks where it went.",
    scenes: [
      {
        id: 1,
        heading: "INT. KITCHEN - MORNING",
        look: "Cold light.",
        shots: [shot("1.1", [2], "Mom", "Where is it?", 2), shot("1.2", [3], "Nate", "Gone.", 2)],
      },
    ],
    clips: [{ id: "c1", shot_ids: ["1.1", "1.2"], seconds: 4, seam: "end" }],
  };
  const saved = await page.request.put(`/api/projects/${id}/breakdown`, { data: breakdown });
  expect(saved.ok()).toBeTruthy();

  await page.goto(`/b/${brandId}/projects/${id}?stage=storyboard`);
  await page.getByRole("button", { name: /Make storyboard/ }).click();
  await expect(page.getByRole("alert")).toContainText("Generation is switched off");
  const jobs = await (await page.request.get("/api/jobs")).json();
  expect(jobs.filter((j: { project_id: number }) => j.project_id === id)).toHaveLength(0);
});

import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// The whole video flow with the free stand-in providers (see start-server.sh): nothing real is
// sent or billed. Reed (the owner) clicks every step from a pasted script to the finished video.
const SCRIPT = [
  "SCENE 1 - KITCHEN",
  "Max stares at the empty bowl.",
  "MAX: Where did the food go?",
  "Mia grins and points at the dog.",
  "MIA: Ask him.",
].join("\n");

test("a script becomes a finished video, step by step, at no cost", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Pipeline Co");
  const made = await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Pipeline test", planned_seconds: 20 } });
  expect(made.ok()).toBeTruthy();
  const id = (await made.json()).id;
  expect((await page.request.put(`/api/projects/${id}/script`, { data: { text: SCRIPT } })).ok()).toBeTruthy();
  const stage = (name: string) => page.goto(`/b/${brandId}/projects/${id}?stage=${name}`);

  // Enhance runs and finds nothing to add to this short script.
  await stage("enhance");
  await page.getByRole("button", { name: /^Suggest directions/ }).click();
  await expect(page.getByText(/already reads well/)).toBeVisible({ timeout: 30_000 });

  // Shots: scenes, clips and shots, with no problems.
  await stage("breakdown");
  await page.getByRole("button", { name: /Make shots/ }).click();
  await expect(page.getByRole("region", { name: "Scene 1" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /Next: Storyboard/ }).click();

  // Storyboard: a frame for each clip, a still for each, all approved.
  await page.getByRole("button", { name: /Make the storyboard/ }).click();
  await expect(page.getByRole("listitem", { name: "Frame c1" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /^Make \d+ stills?/ }).click();
  const approve = page.getByRole("button", { name: "Approve", exact: true });
  await expect(approve.first()).toBeVisible({ timeout: 60_000 });
  while (await approve.count()) {
    await approve.first().click();
    await expect(page.getByText("✓ Approved").first()).toBeVisible();
  }
  await page.getByRole("button", { name: /Next: Clips/ }).click();

  // Clips: write the prompts, make a take, approve it. Final video: put the clips together.
  await page.getByRole("button", { name: /Write clip prompts/ }).click();
  await expect(page.getByRole("listitem", { name: "Clip c1" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /^Make clip/ }).first().click();
  await expect(page.getByRole("button", { name: "Approve take" }).first()).toBeVisible({ timeout: 90_000 });
  await page.getByRole("button", { name: "Approve take" }).first().click();
  await expect(page.getByRole("button", { name: "Undo approval" }).first()).toBeVisible();
  await page.getByRole("button", { name: /Next: Final video/ }).click();
  await page.getByRole("button", { name: "Make the video", exact: true }).click();
  await expect(page.getByRole("link", { name: "Download MP4" })).toBeVisible({ timeout: 60_000 });

  // It cost nothing real: every job is a stand-in, and the video is a real MP4 file.
  const video = await (await page.request.get(`/api/projects/${id}/video`)).json();
  const file = await page.request.get(`/api/files/${video.file_id}`);
  expect(file.headers()["content-type"]).toBe("video/mp4");
  expect((await file.body()).length).toBeGreaterThan(1000);
});

import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// Hooks as versions in the new look, on the stand-ins (free; nothing is sent to a provider): a script with two
// openings is sent as it is, made as one video, and delivered with a version for each over the same body.
// The switch moves between them, each has its own file, and another take of a clip of the body puts both out of date
// until the one free press makes the cuts again. Each press is one request, and the page sends nothing else.
test("at 1440, a script with two hooks is made as one video with two versions: the switch, a file for each, and a body clip's new take puts both out of date", async ({ page }) => {
  test.setTimeout(600_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.goto(`/s${new URL(page.url()).pathname}`);
  const script = ["HOOK 1", "SCENE 1 — EXT. LOT — DAY", `MIA: They almost got her ${Date.now()}.`, "HOOK 2", "SCENE 2 — INT. HALL — DAY", "DANA: My phone rang twice.", "BODY", "SCENE 3 — INT. KITCHEN — DAY", "NATE: Download fomo through the link in my bio."].join("\n");
  await page.getByRole("textbox", { name: "Your script" }).fill(script);
  await expect(page.getByText(/^2 hooks · /)).toBeVisible(); // the script was read as two hooks; nothing to choose
  const send = page.waitForRequest((r) => r.method() === "POST" && new URL(r.url()).pathname === "/api/freestyles");
  await page.getByRole("button", { name: /^Make it (about|up to) \$\d+\.\d\d$/ }).click({ timeout: 30_000 });
  expect((await send).postDataJSON()).toMatchObject({ text: script });
  expect((await send).postDataJSON()).not.toHaveProperty("hooks");
  await expect(page).toHaveURL(/\/s\/b\/\d+\/videos\/\d+$/, { timeout: 30_000 });
  const writes: string[] = [];
  page.on("request", (r) => r.method() !== "GET" && new URL(r.url()).pathname.startsWith("/api/") && writes.push(`${r.method()} ${new URL(r.url()).pathname.replace(/\d+/g, "N")}${new URL(r.url()).search} ${r.postData() ?? ""}`.trim()));

  const chat = page.getByRole("region", { name: "The director" });
  const film = page.getByRole("region", { name: "The video" });
  const header = page.locator("header.vhead");
  const start = chat.getByRole("region", { name: "The plan and the cast" });
  const making = start.getByRole("list", { name: "What it will make" }).getByRole("listitem");
  await expect(making).toHaveCount(3, { timeout: 90_000 }); // a clip for each hook, and one for the body
  await expect(start.getByText("The plan is on the right: 3 clips for one video with 2 versions, each hook over the same body, at one price for all.")).toBeVisible();
  await expect(making.nth(0)).toContainText("V1");
  await expect(making.nth(1)).toContainText("V2");
  await expect(making.nth(2)).toContainText("all 2 versions");
  await film.getByRole("button", { name: "Plan" }).click();
  await expect(film.getByRole("heading", { level: 3 })).toContainText(["V1", "V2", "body, in all 2 versions"]);
  await start.getByRole("button", { name: /^Approve and film/ }).click();
  await expect(header.getByText("Delivered", { exact: true })).toBeVisible({ timeout: 300_000 });
  await expect(chat.getByText(/It has 2 versions, one for each opening of the script over the same body/)).toBeVisible();

  // The switch: each version plays its own file, and the one on screen is kept in the address.
  const cut = film.getByLabel("The cut", { exact: true });
  const version = film.getByRole("group", { name: "Version" });
  await film.getByRole("button", { name: "Cut", exact: true }).click();
  await expect(version.getByRole("button", { name: "V1" })).toHaveAttribute("aria-pressed", "true");
  await expect(cut).toBeVisible();
  const first = (await cut.getAttribute("src"))!;
  await version.getByRole("button", { name: "V2" }).click();
  await expect(page).toHaveURL(/\?v=2$/);
  await expect(cut).not.toHaveAttribute("src", first, { timeout: 60_000 }); // its own cut, once it is made
  const second = (await cut.getAttribute("src"))!;
  for (const src of [first, second]) expect((await page.request.get(src)).headers()["content-type"]).toContain("video/");
  await expect(header.getByRole("link", { name: "Download" })).toHaveAttribute("download", / V2\.mp4$/);
  await page.reload();
  await expect(version.getByRole("button", { name: "V2" })).toHaveAttribute("aria-pressed", "true");
  await expect(cut).toHaveAttribute("src", second);

  // Another take of the body's clip: both versions are out of date, and one free press makes both cuts again.
  await film.getByRole("button", { name: /^Clip 3, / }).click();
  await film.getByRole("group", { name: "The picked clip" }).getByRole("button", { name: /^Another take/ }).click();
  await expect(film.getByText("V1 and V2 need a new cut.")).toBeVisible({ timeout: 120_000 });
  await film.getByRole("button", { name: "Make the cuts free" }).click();
  await expect(cut).not.toHaveAttribute("src", second, { timeout: 120_000 }); // the second version's new cut
  await expect(film.getByText(/need(s)? a new cut\./)).toBeHidden({ timeout: 60_000 });
  expect(writes).toEqual(['POST /api/asks/N/answer {"how":"make_it"}', 'POST /api/projects/N/clips/N/generate {"note":""}', "POST /api/projects/N/cut"]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});

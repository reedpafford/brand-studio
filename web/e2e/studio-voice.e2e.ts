import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// Changing the voice of a narrated video from its Cast view in the new look, on the stand-ins (free; nothing is sent to
// a provider): a short narrated video is made end to end, then another voice is picked. The pick is two requests, the
// video's voice setting and Carry on, and the run's start card comes up saying the voice. It stops there: nothing is
// read before the card's own press, which this never presses. On the way: a Carry on that is refused (answered here,
// once, in the server's place) leaves the voice set and waiting, and Undo puts the setting back.
const SHOTS = process.env.VOICE_SHOTS; // a folder: the row, the menu, the waiting row and the card's line are saved there
const REFUSED = "The director is already working on this video.";

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`at ${width}, a narrated video's voice is changed from its Cast view: the setting, then Carry on, and the start card says the voice`, async ({ page }) => {
    test.setTimeout(600_000);
    await page.setViewportSize({ width, height });
    const shot = async (name: string) => SHOTS && (await page.waitForTimeout(300), await page.screenshot({ path: `${SHOTS}/${name}-${width}x${height}.png` }));
    await signIn(page, "reed@example.com");
    await onBrand(page, "fomo");
    await page.goto(`/s${new URL(page.url()).pathname}`);
    await page.getByRole("button", { name: /^Format: / }).click();
    await page.getByRole("menu", { name: "Format" }).getByRole("menuitemradio", { name: /^Narrated/ }).click();
    await page.getByRole("textbox", { name: "Your script" }).fill(`Bo would never touch his bowl. Then we found Iron Paws. Now he licks it clean, every time. ${Date.now()}`);
    await page.getByRole("button", { name: /^Make it (about|up to) \$\d+\.\d\d$/ }).click({ timeout: 30_000 });
    await expect(page).toHaveURL(/\/s\/b\/\d+\/videos\/\d+$/, { timeout: 30_000 });
    const writes: string[] = [];
    page.on("request", (r) => r.method() !== "GET" && new URL(r.url()).pathname.startsWith("/api/") && writes.push(`${r.method()} ${new URL(r.url()).pathname.replace(/\d+/g, "N")} ${r.postData() ?? ""}`.trim()));

    const chat = page.getByRole("region", { name: "The director" });
    const film = page.getByRole("region", { name: "The video" });
    await chat.getByRole("region", { name: "The plan and the cast" }).getByRole("button", { name: /^Approve and film/ }).click({ timeout: 120_000 });
    await expect(page.locator("header.vhead").getByText("Delivered", { exact: true })).toBeVisible({ timeout: 420_000 });

    await film.getByRole("button", { name: "Cast" }).click();
    const row = film.getByRole("region", { name: "Narration voice" });
    const change = row.getByRole("button", { name: "Change the voice" });
    await change.scrollIntoViewIfNeeded();
    const was = (await row.locator("b").textContent())!; // the voice the director picked
    await shot("1-row");
    await change.click();
    const menu = page.getByRole("menu", { name: "Narration voice" });
    await expect(menu.getByRole("menuitemradio", { checked: true }).locator("b")).toHaveText(was); // the one it is read in
    await shot("2-menu");
    const other = menu.getByRole("menuitemradio", { checked: false }).first();
    const name = (await other.locator("b").textContent())!;

    await page.route("**/api/projects/*/director/carry-on", (r) => r.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: REFUSED }) }), { times: 1 });
    await other.click(); // free: only the setting
    await expect(row.locator("b")).toHaveText(name);
    await row.getByRole("button", { name: `Read it in ${name}` }).click();
    await expect(row.getByRole("alert")).toHaveText(REFUSED);
    await expect(row.getByText(`not read yet · the video still plays in ${was}`)).toBeVisible();
    await expect(row.getByRole("button", { name: `Read it in ${name}` })).toBeVisible();
    await shot("3-waiting");
    await row.getByRole("button", { name: "Undo" }).click();
    await expect(row.locator("b")).toHaveText(was);

    await change.click();
    await other.click();
    await row.getByRole("button", { name: `Read it in ${name}` }).click();
    const round = chat.getByRole("region", { name: "Round 2" });
    await expect(round.getByText(`The narration is read again in the ${name} voice.`)).toBeVisible({ timeout: 120_000 });
    // The chat side is on screen with the card in it: its press can be pressed where it is, under nothing.
    const press = round.getByRole("button", { name: /^Make round 2 (about|up to) \$\d+\.\d\d$/ });
    await expect.poll(() => press.evaluate((el) => ((r) => el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)))(el.getBoundingClientRect()))).toBe(true);
    await shot("4-card");
    const set = expect.stringMatching(/^POST \/api\/projects\/N\/settings \{"voice":"(stock:.+|voice:\d+)"\}$/);
    expect(writes).toEqual(['POST /api/asks/N/answer {"how":"make_it"}', set, "POST /api/projects/N/director/carry-on", 'POST /api/projects/N/settings {"voice":null,"undo":true}', set, "POST /api/projects/N/director/carry-on"]);
    await expect(row.locator("b")).toHaveText(name);
    await expect(row.getByRole("button", { name: /^(Read it in|Change the voice|Undo)/ })).toHaveCount(0); // the card is the press
    await row.scrollIntoViewIfNeeded();
    await shot("5-waiting-with-card");
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  });
}

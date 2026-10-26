// QA-Live click-through of the live Brand Studio site, run one step at a time:
//   node qa-live/full-flow.js <step> [--paid]
// Steps (in order): owner-signup ig-link draft-undo script editor-invite editor-video release cleanup
// Secrets: the owner invite is read from BS_QA_OWNER_INVITE and never printed. Passwords are random and
// kept only in memory; signed-in cookies go to $QA_DIR/state (outside the repo, never committed).
// Money: a paid button is pressed only with --paid, only after its shown price is read, and never past
// LIMIT credits in total. Every paid press is written to $QA_DIR/costs.json.
const { chromium } = require("playwright");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BS_BASE || "https://srv2091584.hstgr.cloud";
const QA_DIR = process.env.QA_DIR || path.join(require("os").tmpdir(), "bs-qa-live");
const REEL = path.join(__dirname, "reel-De3QNNgu_9S.mp4");
const IG = "https://www.instagram.com/reels/De3QNNgu_9S/";
const BRAND = "fomo";
const TITLE = "QA live reel";
const EDITOR_EMAIL = "qa-editor@example.com";
const LIMIT = 140; // credits ($15 at $0.1028)
const PAID = process.argv.includes("--paid");
for (const d of ["state", "shots", "dl"]) fs.mkdirSync(path.join(QA_DIR, d), { recursive: true, mode: 0o700 });

const ledgerFile = path.join(QA_DIR, "costs.json");
const ledger = fs.existsSync(ledgerFile) ? JSON.parse(fs.readFileSync(ledgerFile, "utf8")) : [];
const spent = () => ledger.reduce((t, r) => t + r.credits_shown, 0);
const counterFile = path.join(QA_DIR, "shots", ".n");
let n = fs.existsSync(counterFile) ? Number(fs.readFileSync(counterFile, "utf8")) : 0;
const password = () => crypto.randomBytes(18).toString("base64url");

async function open(browser, who, width = 1440) {
  const state = path.join(QA_DIR, "state", `${who}.json`);
  const ctx = await browser.newContext({ baseURL: BASE, viewport: { width, height: 900 }, acceptDownloads: true, ...(fs.existsSync(state) ? { storageState: state } : {}) });
  const page = await ctx.newPage();
  page.setDefaultTimeout(30_000);
  const shot = async (name) => {
    n += 1;
    fs.writeFileSync(counterFile, String(n));
    const file = path.join(QA_DIR, "shots", `${String(n).padStart(3, "0")}-${who}-${name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    console.log("shot", path.basename(file));
    if (width > 390) {
      // Same screen at phone width, for the report when it looks wrong.
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({ path: file.replace(/\.png$/, "-390.png"), fullPage: true });
      await page.setViewportSize({ width, height: 900 });
    }
  };
  const save = async () => {
    await ctx.storageState({ path: state });
    fs.chmodSync(state, 0o600);
  };
  return { ctx, page, shot, save };
}

/** Reads the price inside a paid button, checks the budget, presses it (only with --paid), and logs it. */
async function pay(page, button, step) {
  await button.waitFor();
  const label = (await button.innerText()).replace(/\s+/g, " ").trim();
  const m = label.match(/(\d+)\s*credits?/i);
  const credits = m ? Number(m[1]) : /free/i.test(label) ? 0 : NaN;
  if (Number.isNaN(credits)) throw new Error(`STOP: no price on "${label}" (${step})`);
  if (spent() + credits > LIMIT) throw new Error(`STOP: "${label}" would take the total to ${spent() + credits} of ${LIMIT} credits (${step})`);
  if (!PAID && credits > 0) throw new Error(`STOP: "${label}" costs ${credits} credits; rerun with --paid (${step})`);
  if (await button.isDisabled()) throw new Error(`STOP: "${label}" is disabled (${step})`);
  await button.click();
  ledger.push({ step, label, credits_shown: credits, at: new Date().toISOString() });
  fs.writeFileSync(ledgerFile, JSON.stringify(ledger, null, 2));
  console.log(`paid ${credits} · total ${spent()} of ${LIMIT} · ${step}`);
}

const steps = (page) => page.getByRole("list", { name: "Steps" });
const goStep = (page, name) => steps(page).getByRole("button", { name, exact: true }).click();
const brandHome = async (page) => {
  await page.goto("/");
  const sw = page.getByRole("button", { name: /^Brand: / });
  if (!(await sw.innerText()).includes(BRAND)) {
    await sw.click();
    await page.getByRole("menuitemradio", { name: BRAND }).click();
  }
  await page.getByRole("heading", { name: "Scripts", exact: true }).waitFor();
};
const openScript = async (page) => {
  await brandHome(page);
  await page.getByRole("link", { name: TITLE, exact: true }).first().click();
};

const flow = {
  // 0. Accept the owner invite as "QA Owner" with a random password.
  async "owner-signup"(b) {
    const invite = process.env.BS_QA_OWNER_INVITE;
    if (!invite) throw new Error("STOP: BS_QA_OWNER_INVITE is not set");
    const { page, shot, save } = await open(b, "owner");
    await page.goto(invite);
    await page.getByLabel("Your name").fill("QA Owner");
    await page.getByLabel("Choose a password (10 or more characters)").and(page.locator("input")).fill(password());
    await page.getByRole("button", { name: "Create my account" }).click();
    await page.getByRole("button", { name: "Account menu" }).waitFor();
    await save();
    await page.goto("/team");
    await shot("team-shows-role");
    console.log("me:", JSON.stringify(await (await page.request.get("/api/me")).json().catch(() => null)));
  },

  // 1. The Instagram link, once. A priced read is not pressed here.
  async "ig-link"(b) {
    const { page, shot } = await open(b, "owner");
    await brandHome(page);
    await page.getByRole("link", { name: "New script" }).first().click();
    await page.getByRole("radio", { name: "Import a reel" }).click();
    await shot("import-a-reel");
    await page.getByLabel("Paste an Instagram reel link").fill(IG);
    await page.getByRole("button", { name: "Get the reel" }).click();
    const outcome = page.getByRole("alert").or(page.getByText(/^(Got the reel|Getting the reel…)$/));
    await outcome.first().waitFor({ timeout: 60_000 });
    await shot("after-get-the-reel");
    await page.getByText("Getting the reel…").waitFor({ state: "hidden", timeout: 180_000 }).catch(() => {});
    await shot("link-result");
    console.log("url:", page.url());
    console.log("result:", (await page.locator("main").innerText()).slice(0, 1500));
  },

  // 2. A throwaway draft (Paste words, nothing paid): delete, Undo, then delete for good.
  async "draft-undo"(b) {
    const { page, shot } = await open(b, "owner");
    await brandHome(page);
    await page.getByRole("link", { name: "New script" }).first().click();
    await page.getByLabel("Title").fill("QA throwaway");
    await page.getByLabel("What it's for").fill("Deleted by QA to test Undo.");
    await page.getByRole("button", { name: "Create script" }).click();
    await page.getByRole("button", { name: "Paste or write it yourself" }).click();
    await page.getByLabel("Your script").fill("QA: Testing undo.");
    await page.getByRole("button", { name: "Save script" }).click();
    await shot("draft-made");
    await page.getByRole("link", { name: "Scripts", exact: true }).first().click();
    const del = async () => {
      await page.getByRole("button", { name: "More for QA throwaway" }).click();
      await page.getByRole("menuitem", { name: "Delete script" }).click();
      await shot("delete-confirm");
      await page.getByRole("alertdialog").getByRole("button", { name: "Delete", exact: true }).click();
      await page.getByText('Deleted "QA throwaway".').waitFor();
    };
    await del();
    await shot("deleted-with-undo");
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await page.getByText('Restored "QA throwaway".').waitFor();
    await shot("restored");
    await del();
    await page.getByRole("button", { name: "Deleted and archived" }).click().catch(() => {});
    await shot("deleted-and-archived");
  },

  // 3. Reel upload → Description → Script → Directions → Variations (1) → Cast → Breakdown → Publish.
  async script(b) {
    const { page, shot } = await open(b, "owner");
    await brandHome(page);
    await page.getByRole("link", { name: "New script" }).first().click();
    await page.getByRole("radio", { name: "Import a reel" }).click();
    await page.getByLabel("Choose a video file").setInputFiles(REEL);
    await page.getByText(/^Got the reel$/).waitFor({ timeout: 180_000 });
    await shot("description-reel-got");
    // Title the script so later steps can find it, if the Description step has a Title box.
    const title = page.getByLabel("Title");
    if (await title.count()) {
      await title.fill(TITLE);
      await title.blur();
    }
    await goStep(page, "Script");
    await shot("script-step");
    await pay(page, page.getByRole("button", { name: /^Write from the reference/ }), "Script: Write from the reference");
    await page.getByRole("list", { name: "Script text" }).waitFor({ timeout: 300_000 });
    await shot("script-written");

    await goStep(page, "Directions");
    await pay(page, page.getByRole("button", { name: /^Suggest directions/ }), "Directions: Suggest directions");
    const add = page.getByRole("button", { name: /^Add \d+ directions?$/ });
    await add.or(page.getByText("This script already reads well. Nothing to suggest.")).waitFor({ timeout: 180_000 });
    await shot("directions-suggested");
    if (await add.isVisible()) {
      await page.getByRole("button", { name: /^Accept: / }).first().click();
      await page.getByRole("button", { name: "Add 1 direction" }).click();
      await page.getByText("Added 1 direction.").waitFor();
    }
    await shot("directions-done");

    await goStep(page, "Variations");
    await page.getByRole("radio", { name: "1", exact: true }).click();
    await pay(page, page.getByRole("button", { name: /^Write 1 variation/ }), "Variations: Write 1 variation");
    const vb = page.getByLabel("Version B", { exact: true });
    await vb.waitFor({ timeout: 300_000 });
    await shot("variation-b");
    await vb.getByRole("button", { name: "Approve" }).click();

    await goStep(page, "Cast");
    const find = page.getByRole("button", { name: /^Find roles in the script/ });
    if (await find.count()) {
      await pay(page, find, "Cast: Find roles in the script");
      await page.getByText(/^\d+ roles? · \d+ locked$/).waitFor({ timeout: 180_000 });
    }
    await shot("cast-roles");
    const lock = page.getByRole("button", { name: /^Lock .+ to a look$/ }).first();
    await lock.click();
    await shot("lock-panel");
    const choice = page.getByRole("button", { name: /^Lock to / }).first();
    if (await choice.isEnabled()) await choice.click();
    else console.log("no approved look to lock to:", await choice.getAttribute("aria-label"));
    await shot("cast-one-locked");

    await page.getByRole("button", { name: "Next: Breakdown" }).click();
    await pay(page, page.getByRole("button", { name: /^Make the breakdown/ }), "Breakdown preview: Make the breakdown");
    await page.getByText(/^Planned · \d+ s/).waitFor({ timeout: 300_000 });
    await shot("breakdown-preview");

    await page.getByRole("button", { name: "Next: Publish" }).click();
    await shot("publish-step");
    await page.getByRole("button", { name: /^Publish \d+ versions?/ }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Publish", exact: true }).click();
    await page.getByText(/^Published\./).waitFor();
    await shot("published");
  },

  // 4. Owner invites QA Editor; the editor accepts in a second context.
  async "editor-invite"(b) {
    const { page, shot } = await open(b, "owner");
    await page.goto("/team");
    await page.getByRole("button", { name: "Invite someone" }).click();
    await page.getByLabel("Email to invite").fill(EDITOR_EMAIL);
    await page.getByLabel("Role").selectOption("editor");
    await page.getByRole("dialog").getByRole("button", { name: /invite|link/i }).last().click();
    const linkBox = page.getByLabel("Invite link");
    await linkBox.waitFor();
    const link = await linkBox.inputValue(); // kept in memory only; no screenshot while it shows
    await page.getByRole("dialog").getByRole("button", { name: /^(Done|Close)$/ }).first().click().catch(() => page.keyboard.press("Escape"));
    await shot("team-invite-waiting");
    const ed = await open(b, "editor");
    await ed.page.goto(link);
    await ed.page.getByLabel("Your name").fill("QA Editor");
    await ed.page.getByLabel("Choose a password (10 or more characters)").and(ed.page.locator("input")).fill(password());
    await ed.page.getByRole("button", { name: "Create my account" }).click();
    await ed.page.getByRole("button", { name: "Account menu" }).waitFor();
    await ed.save();
    await ed.shot("editor-signed-in");
  },

  // 5. Editor: version from the library → Breakdown → Assets → Storyboard → Clips (one Redo with a note) → zip.
  async "editor-video"(b) {
    const { page, shot } = await open(b, "editor");
    await brandHome(page);
    await shot("editor-library");
    await page.getByRole("link", { name: /^Version [A-Z], ready to make$/ }).first().click();
    await shot("version-panel");
    await page.getByRole("dialog").getByRole("button", { name: "Make this version" }).click();
    await page.waitForURL(/\/videos\/\d+/);
    await shot("video-breakdown");
    const make = page.getByRole("button", { name: /^Make shots/ });
    if (await make.count()) await pay(page, make, "Editor Breakdown: Make shots");
    await page.getByRole("button", { name: "Next: Assets" }).click({ timeout: 300_000 });
    await shot("assets");
    const look = page.getByRole("button", { name: /^Make a look/ }).first();
    if (await look.count()) {
      await pay(page, look, "Editor Assets: Make a look");
      await page.waitForTimeout(5000);
      await shot("look-started");
    } else console.log("no Make a look button on Assets");
    await page.getByRole("button", { name: "Next: Storyboard" }).click({ timeout: 600_000 });
    await pay(page, page.getByRole("button", { name: /^Make storyboard/ }), "Editor Storyboard: Make storyboard");
    const approve = page.getByRole("button", { name: "Approve", exact: true });
    await approve.first().waitFor({ timeout: 600_000 });
    await shot("storyboard");
    while (await approve.count()) await approve.first().click();
    await page.getByRole("button", { name: /^Next: Clips/ }).click();
    await pay(page, page.getByRole("button", { name: /^Write clip prompts/ }), "Editor Clips: Write clip prompts");
    await page.getByRole("button", { name: /^Prompt for \w+ looks good$/ }).first().waitFor({ timeout: 300_000 });
    for (const ok of await page.getByRole("button", { name: /^Prompt for \w+ looks good$/ }).all()) await ok.click();
    await shot("clip-prompts");
    for (;;) {
      const mk = page.getByRole("button", { name: /^Make clip/ }).first();
      if (!(await mk.count())) break;
      await pay(page, mk, "Editor Clips: Make clip");
      await page.waitForTimeout(2000);
    }
    await page.getByRole("button", { name: "✓ Looks good" }).first().waitFor({ timeout: 900_000 });
    await shot("clips-made");
    await page.getByRole("button", { name: /^Redo/ }).first().click();
    await page.locator("textarea").last().fill("Slower camera move, keep the face in frame.");
    await pay(page, page.getByRole("button", { name: /^Redo/ }).last(), "Editor Clips: Redo with a note");
    await page.waitForTimeout(5000);
    await shot("redo-started");
    console.log("Wait for the redo, mark every clip Looks good, then run the download with: editor-download");
  },

  async "editor-download"(b) {
    const { page, shot } = await open(b, "editor");
    await page.goto(process.env.QA_VIDEO_URL || "/");
    for (const ok of await page.getByRole("button", { name: "✓ Looks good" }).all()) await ok.click().catch(() => {});
    await page.getByRole("button", { name: /^Next: Downloads/ }).click();
    await shot("downloads");
    const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 300_000 }), page.getByText("Download all clips (.zip)").click()]);
    const zip = path.join(QA_DIR, "dl", "clips.zip");
    await dl.saveAs(zip);
    console.log("zip saved", zip, fs.statSync(zip).size, "bytes");
  },

  // 6. Owner starts a second version (nothing generated) and releases it.
  async release(b) {
    const { page, shot } = await open(b, "owner");
    await brandHome(page);
    await page.getByRole("link", { name: /^Version [A-Z], ready to make$/ }).first().click();
    await page.getByRole("dialog").getByRole("button", { name: "Make this version" }).click();
    await page.waitForURL(/\/videos\/\d+/);
    await shot("second-version-started");
    await page.getByRole("button", { name: /^More for / }).first().click();
    await page.getByRole("menuitem", { name: "Release this version" }).click();
    await shot("release-confirm");
    await page.getByRole("alertdialog").getByRole("button", { name: /^Release/ }).click();
    await page.getByRole("heading", { name: "Scripts", exact: true }).waitFor();
    await shot("released");
  },

  // 8. Owner removes QA Editor from the team (the script and QA Owner stay).
  async cleanup(b) {
    const { page, shot } = await open(b, "owner");
    await page.goto("/team");
    await page.getByRole("button", { name: /Remove QA Editor/ }).click();
    await page.getByRole("button", { name: "Remove", exact: true }).click();
    await shot("editor-removed");
  },
};

(async () => {
  const step = process.argv[2];
  if (!flow[step]) {
    console.log("steps:", Object.keys(flow).join(" "));
    process.exit(1);
  }
  const browser = await chromium.launch();
  try {
    await flow[step](browser);
    console.log(`done ${step} · ${spent()} of ${LIMIT} credits so far`);
  } catch (e) {
    console.log(String(e.message).split("\n").slice(0, 6).join("\n"));
    process.exitCode = 2;
  } finally {
    await browser.close();
  }
})();

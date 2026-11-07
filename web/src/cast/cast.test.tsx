import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { clipsText } from "./CastPane";

// The Cast tab (v6 S5-01 to S5-04, P-09, S-gaps-05 L3, S-gaps-07): each role's picture, where it came from, its state and
// the one press that moves it on; the presenter's face, voice and how they appear; the places.
const project = { id: 50, brand_id: 1, name: "Three dimes to a penthouse", freestyle_id: null, aspect_ratio: "9:16", look: "house", credits_used: 11, budget_credits: 189, created_by_id: 1, created_by_name: "Reed", folder_id: 4, script_draft_id: 7, product_variants: {}, plan_status: "approved", kind: "story" };
const money = (credits: number, usd: number | null) => ({ credits, usd });
const head = (rate: number | null) => ({ title: "Three dimes to a penthouse", status: { kind: "need", words: "Needs you", reason: null, at: null, made: 0, total: 0 }, spent: money(11, rate && 1.1), up_to: money(189, rate && 19.4), budget: money(189, rate && 19.4), folder: { id: 4, name: "House remakes" }, format: "Dialogue", style: "House", seconds: 65, song: false, usd_per_credit: rate });
const role = (o: object) => ({ kind: "character", ref: "char:5", role: "Marcus", library_item_id: 5, name: "Marcus", locked: false, sheet_status: "approved", ready: true, slot_id: 1, description: "Main character", shots: 9, clip_ids: ["c1", "c2", "c3"], sheet_file_id: 70, only_here: "video", own_look_id: 5, look_credits: 0.78, script_unlock: false, drawing_job_id: null, photo_file_id: null, library_version: null, ...o });
const marcus = role({});
const jade = role({ ref: "char:8", role: "Jade", library_item_id: 8, name: "Goth GF", locked: true, slot_id: 2, description: "Girlfriend", clip_ids: ["c1"], only_here: null, own_look_id: null, library_version: 4, sheet_file_id: 71 });
const chase = role({ ref: "slot:3", role: "Chase", library_item_id: null, name: "", sheet_status: "missing", slot_id: 3, description: "Rival", clip_ids: ["c2", "c3", "c4"], sheet_file_id: null, only_here: null, own_look_id: null, facts: { age_range: null, gender: { value: "male", guessed: false }, occupation: null } });
const locks = (roles: string[] = [], outfits: Record<string, string> = {}) => ({ locks: { cast: false, look: false, length: false, song: false, screens: [], roles }, outfits });
const item = (ref: string, name: string, o: object = {}) => ({ ref, kind: "character", name, library_item_id: null, version: null, source: "video", preview_file_id: null, readiness: "ready", approval: "new", sig: `sig-${ref}`, clip_ids: [], ...o });
const gate = (items: object[], o: object = {}) => ({ state: "ready", approved_by: null, approved_at: null, asked: true, items, waiting: [], not_ready: [], paused_clips: [], update: { stills: [], clips: [], credits: 0 }, ...o });
const firstSet = gate([item("char:5", "Marcus"), item("char:8", "Goth GF", { source: "library", version: 4, library_item_id: 8 }), item("slot:3", "Chase", { source: null, readiness: "needs_look" })], { state: "not_ready", waiting: ["Marcus", "Goth GF"], not_ready: [{ ref: "slot:3", name: "Chase", why: "Chase needs a look" }] });
const saved = [{ id: 21, kind: "character", name: "Chase (rival)", sheet_file_id: 90, sheet_status: "approved", brand_ids: [1], image_file_ids: [], outfits: [], version: 2, used_in_count: 3 }];

function server(me: object, rows: object[], routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
    "GET /looks": [200, [{ id: "house", name: "House", blurb: "", on: true, own_sample: false, lanes: [] }]],
    "GET /jobs": [200, []],
    "GET /projects/50": [200, project],
    "GET /projects/50/director": [200, { status: "waiting", ended: "", turns: [], credits: 11, spent_usd: null, start_blocked: "", thread: [], unread: 0, run_price: 0 }],
    "GET /projects/50/idea": [200, head(me === editor ? null : 0.1028)],
    "GET /projects/50/clips": [200, [1, 2, 3].map((n) => ({ id: n, clip_id: `c${n}`, takes: [], approved: false }))],
    "GET /projects/50/storyboard": [200, []],
    "GET /projects/50/assets": [200, rows],
    "GET /projects/50/assets/maybe-same": [200, []],
    "GET /projects/50/host": [200, { on: false, state: "none", pieces: [], credits: 0, presenter_id: null, voice: null }],
    "GET /projects/50/video": [404, { detail: "none" }],
    "GET /projects/50/locks": [200, locks()],
    "GET /library/character": [200, saved],
    ...routes,
  });
}
const open = () => renderApp("/b/1/videos/50?tab=cast");
afterEach(() => vi.unstubAllGlobals());

test("clips read as a run or a list", () => {
  expect(clipsText(["c2", "c3", "c4"])).toBe("Clips 2–4");
  expect(clipsText(["c7"])).toBe("Clip 7");
  expect(clipsText(["c2", "c5", "c7"])).toBe("Clips 2, 5 and 7");
  expect(clipsText(["c1", "c1b", "c2"])).toBe("Clips 1, 1b and 2"); // a split clip (QA on #1383): never NaN
  expect(clipsText(["c1b"])).toBe("Clip 1b");
});

test("S5-01 / S-gaps-07: each card says where its look came from and how it stands; one with no look offers the library, Upload and Make one at its up-to price", async () => {
  setViewport(1440);
  server(owner, [marcus, jade, chase], { "GET /projects/50/cast": [200, firstSet] });
  open();
  const m = await screen.findByRole("region", { name: "Marcus" });
  expect(within(m).getByText("Main character · in 3 of 3 clips")).toBeInTheDocument();
  expect(within(m).getByText("Made for this video")).toBeInTheDocument();
  expect(within(m).getByText("Ready to check")).toBeInTheDocument();
  expect(within(m).getByRole("button", { name: "Change…" })).toBeInTheDocument();
  expect(within(m).getByRole("button", { name: "More for Marcus" })).toBeInTheDocument();
  const j = screen.getByRole("region", { name: "Jade" });
  expect(within(j).getByText("From fomo’s library · “Goth GF” v4")).toBeInTheDocument();
  expect(within(j).getByText("Locked on the script")).toBeInTheDocument();
  const c = screen.getByRole("region", { name: "Chase" });
  expect(within(c).getByText("No sheet yet. Clips 2–4 wait for him.")).toBeInTheDocument();
  expect(within(c).getByText("Needs a look")).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "From fomo’s library" })).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "Upload" })).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "Make one · up to $0.09" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Cast & places" })).toBeInTheDocument();
  expect(screen.getByText("Needs you · approve to continue")).toBeInTheDocument();
  expect(screen.getAllByText(/Not ready yet: Chase needs a look\./).length).toBeGreaterThan(0); // the banner, and why Approve waits
  expect(screen.getByRole("button", { name: "Approve cast & places" })).toBeDisabled(); // Chase first
  expect(screen.getByText(/Locked looks are used as they are in every shot/)).toBeInTheDocument();
});
test("S5-04: an editor sees credits, never dollars", async () => {
  setViewport(1440);
  server(editor, [marcus, chase]);
  open();
  const c = await screen.findByRole("region", { name: "Chase" });
  expect(within(c).getByRole("button", { name: "Make one · under 1 credit" })).toBeInTheDocument();
  expect(screen.queryByText(/\$/)).toBeNull();
});

test("Pick, Upload and Make a look each move the role on", async () => {
  setViewport(1440);
  const calls = server(owner, [chase], {
    "PUT /projects/50/assets/slots/3": [200, [chase]],
    "POST /projects/50/assets/slots/3/make-look": [201, [chase]],
    "POST /files": [201, { id: 99, filename: "chase.jpg", content_type: "image/jpeg" }],
    "POST /projects/50/assets/slots/3/upload": [200, [chase]],
  });
  open();
  const c = await screen.findByRole("region", { name: "Chase" });
  await userEvent.click(within(c).getByRole("button", { name: "From fomo’s library" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: /Chase \(rival\)/ }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "PUT /projects/50/assets/slots/3")?.body).toEqual({ library_item_id: 21 }));
  await userEvent.click(within(c).getByRole("button", { name: "Make one · up to $0.09" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/assets/slots/3/make-look")).toBe(true));
  await userEvent.upload(within(c).getByLabelText("Upload a picture for Chase"), new File(["x"], "chase.jpg", { type: "image/jpeg" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/assets/slots/3/upload")?.body).toEqual({ file_id: 99 }));
});

test("More: Lock in this video fixes the look", async () => {
  setViewport(1440);
  const calls = server(owner, [marcus], { "PUT /projects/50/locks": [200, locks(["slot:1"])] });
  open();
  const m = await screen.findByRole("region", { name: "Marcus" });
  await userEvent.click(within(m).getByRole("button", { name: "More for Marcus" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Lock in this video" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "PUT /projects/50/locks")?.body).toEqual({ ...locks(["slot:1"]) }));
  expect(await screen.findByText("Marcus’s look is locked in this video.")).toBeInTheDocument();
});
test("S5-03 outfit: Outfit for this video saves it on the video; Use the sheet's outfit clears it", async () => {
  setViewport(1440);
  const calls = server(owner, [marcus], { "GET /projects/50/locks": [200, locks([], { "char:5": "rain-soaked green hoodie" })], "PUT /projects/50/locks": [200, locks()] });
  open();
  const m = await screen.findByRole("region", { name: "Marcus" });
  expect(await within(m).findByText("Outfit for this video: rain-soaked green hoodie. The sheet still sets the face.")).toBeInTheDocument();
  await userEvent.click(within(m).getByRole("button", { name: "More for Marcus" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Use the sheet’s outfit" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "PUT /projects/50/locks")?.body).toEqual({ ...locks([], { "char:5": "" }) }));
});

test("a role locked on an unpublished script can be unlocked by its author or the owner", async () => {
  setViewport(1440);
  const calls = server(owner, [{ ...jade, script_unlock: true }], { "DELETE /projects/50/assets/slots/2/script-lock": [200, [jade]] });
  open();
  const j = await screen.findByRole("region", { name: "Jade" });
  await userEvent.click(within(j).getByRole("button", { name: "More for Jade" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Unlock on the script" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "DELETE /projects/50/assets/slots/2/script-lock")).toBe(true));
});

test("S5-03 drawing: the sheet is being drawn, with its price and Cancel", async () => {
  setViewport(1440);
  const calls = server(owner, [role({ role: "Chase", slot_id: 3, sheet_status: "drawing", sheet_file_id: null, drawing_job_id: 77 })], { "POST /jobs/77/cancel": [200, {}] });
  open();
  const c = await screen.findByRole("region", { name: "Chase" });
  expect(within(c).getByText("Drawing")).toBeInTheDocument();
  expect(within(c).getByText("Drawing a front, side and back sheet · up to $0.09 · about 30 s")).toBeInTheDocument();
  await userEvent.click(within(c).getByRole("button", { name: "Cancel" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /jobs/77/cancel")).toBe(true));
});

test("Change… redraws a look made for this video from the note (priced); a saved one's note is asked of the director", async () => {
  setViewport(1440);
  const bo = role({ ref: "char:21", role: "Bo", name: "Chase (rival)", library_item_id: 21, only_here: null, own_look_id: null, slot_id: 9 });
  const calls = server(owner, [marcus, bo], { "POST /library/character/5/sheet": [201, {}], "GET /models": [200, []], "POST /projects/50/director/messages": [201, {}] });
  open();
  const m = await screen.findByRole("region", { name: "Marcus" });
  await userEvent.click(within(m).getByRole("button", { name: "Change…" }));
  await userEvent.type(within(m).getByLabelText("Change Marcus…"), "older, greyer beard");
  await userEvent.click(within(m).getByRole("button", { name: /Change it · up to/ }));
  await vi.waitFor(() => expect((calls.find((x) => x.key === "POST /library/character/5/sheet")?.body as { change: string }).change).toBe("older, greyer beard"));
  const b = screen.getByRole("region", { name: "Bo" });
  await userEvent.click(within(b).getByRole("button", { name: "Change…" }));
  await userEvent.type(within(b).getByLabelText("Change Bo…"), "a red coat");
  await userEvent.click(within(b).getByRole("button", { name: "Ask the director" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/director/messages")?.body).toEqual({ text: "Bo: a red coat" }));
});
test("S5-01: two roles that may be one person show as one card: Merge into one, with Undo, or They're different", async () => {
  setViewport(1440);
  const mom = role({ ref: "char:30", role: "Mom", name: "Mom", library_item_id: 30, slot_id: 5, clip_ids: ["c1"], description: "" });
  const kitchen = role({ ref: "char:31", role: "Mom (kitchen)", name: "Mom (kitchen)", library_item_id: 31, slot_id: 6, clip_ids: ["c2"], description: "" });
  const calls = server(owner, [mom, kitchen], {
    "GET /projects/50/assets/maybe-same": [200, [{ a_slot_id: 5, b_slot_id: 6, into_slot_id: 5, why: "Both are the mother.", undo_token: null }]],
    "POST /projects/50/assets/slots/6/merge": [200, { moved: { shots: ["2.1"], lines: [] }, look_unused: null, token: 4 }],
    "POST /projects/50/assets/merge/undo": [200, []],
  });
  open();
  const pair = await screen.findByRole("region", { name: "Mom and Mom (kitchen)" });
  expect(within(pair).getByText("In 1 clip each")).toBeInTheDocument();
  expect(within(pair).getByText("Check")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Mom" })).toBeNull(); // one card for the two
  await userEvent.click(within(pair).getByRole("button", { name: "Merge into Mom" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/assets/slots/6/merge")?.body).toEqual({ into_slot_id: 5 }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/assets/merge/undo")?.body).toEqual({ token: 4 }));
});

test("S-gaps-07 A: places sit under the characters; one with no look is picked from the library, uploaded, or made for this video", async () => {
  setViewport(1440);
  const bus = { kind: "place", ref: "place:40", role: "", library_item_id: 40, name: "Bus stop in the rain", locked: false, sheet_status: "approved", ready: true, slot_id: null, description: "", shots: 4, clip_ids: ["c1", "c2"], sheet_file_id: 72 };
  const pent = { ...bus, ref: "place:41", library_item_id: 41, name: "The penthouse", sheet_status: "none", sheet_file_id: null, clip_ids: ["c3"], look_credits: 0.78 };
  const set = gate([item("char:5", "Marcus"), item("place:40", "Bus stop in the rain", { kind: "place", source: "video" }), item("place:41", "The penthouse", { kind: "place", source: null, readiness: "needs_look" })], { state: "not_ready" });
  const calls = server(owner, [marcus, bus, pent], {
    "GET /projects/50/cast": [200, set],
    "GET /library/place": [200, [{ id: 60, kind: "place", name: "Rooftop bar", sheet_file_id: 90, sheet_status: "approved", brand_ids: [1], image_file_ids: [], outfits: [], version: 1, used_in_count: 1 }]],
    "PUT /projects/50/cast/places/41": [200, set],
    "POST /projects/50/cast/places/41/make-look": [200, set],
  });
  open();
  expect(await screen.findByRole("heading", { name: "Places" })).toBeInTheDocument();
  const b = screen.getByRole("region", { name: "Bus stop in the rain" });
  expect(within(b).getByText("Made for this video")).toBeInTheDocument();
  const p = screen.getByRole("region", { name: "The penthouse" });
  expect(within(p).getByText("No look yet")).toBeInTheDocument();
  expect(within(p).getByText("Clip 3 waits for it.")).toBeInTheDocument();
  await vi.waitFor(() => expect(within(p).getByRole("button", { name: "From fomo’s library" })).toBeEnabled());
  await userEvent.click(within(p).getByRole("button", { name: "From fomo’s library" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: /Rooftop bar/ }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "PUT /projects/50/cast/places/41")?.body).toEqual({ library_item_id: 60 }));
  await userEvent.click(within(p).getByRole("button", { name: "Make one · up to $0.09" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/cast/places/41/make-look")).toBe(true));
  expect(screen.getByRole("tab", { name: "Cast 3" })).toBeInTheDocument(); // characters and places
});
test("S5-02: a saved presenter is in the cast with the one OK, and before Make it his own voice shows, never a saved clone", async () => {
  setViewport(1440);
  const mark = role({ ref: "char:7", role: "", name: "Mark", library_item_id: 7, slot_id: null, shots: 0, clip_ids: [], only_here: null, own_look_id: null, description: "" });
  const settings = { look: "house", video_model: null, image_model: null, aspect_ratio: "9:16", product_variants: {}, language: "en", video_models: [], image_models: [], shapes: ["9:16"], flavours: {}, presenter: null, presenter_now: "corner", voice: null };
  const clone = { id: 3, name: "Dr. Pickle (cloned)", kind: "cloned", stock_key: null, provider: "minimax", description: "Deep, fixed", sample_url: "/voices/samples/dr-pickle.mp3", preview_file_id: null, sample_file_id: null };
  const roger = { id: null, name: "Roger", kind: "stock", stock_key: "Roger", provider: "elevenlabs", description: "Relaxed man", sample_url: "/voices/samples/Roger.mp3", preview_file_id: null, sample_file_id: null };
  const gate = { state: "ready", approved_by: null, approved_at: null, asked: true, waiting: ["char:7"], not_ready: [], paused_clips: [], update: { stills: [], clips: [], credits: 0 }, can_approve: true, items: [{ ref: "char:7", kind: "character", name: "Mark", library_item_id: 7, version: 1, source: "library", preview_file_id: 70, readiness: "ready", approval: "new", sig: "a", clip_ids: [] }] };
  server(owner, [mark], {
    "GET /projects/50/host": [200, { on: true, state: "none", pieces: [], credits: 0, presenter_id: 7, voice: "Roger" }],
    "GET /projects/50/settings": [200, settings],
    "GET /brands/1/voices": [200, { voices: [clone, roger], clone_credits: 29.18, clone_usd: 3 }],
    "GET /projects/50/cast": [200, gate],
  });
  open();
  const pres = await screen.findByRole("region", { name: "Presenter" });
  expect(await within(pres).findByText(/^Roger · ElevenLabs/)).toBeInTheDocument(); // the server's: his own voice
  expect(within(pres).queryByText(/Dr\. Pickle \(cloned\)/)).toBeNull(); // never the first saved clone
  expect(within(pres).getByText("Mark still")).toBeInTheDocument();
  expect(within(pres).getByText("Mark · saved in fomo")).toBeInTheDocument();
  expect(screen.queryByText("The cast fills in here")).toBeNull();
  expect(screen.getAllByRole("button", { name: "Approve cast & places" }).every((b) => !b.hasAttribute("disabled"))).toBe(true); // the chat card's OK, here too
});

test("S5-02 / S-gaps-05 L3: the presenter's face and voice, and how they appear in this video, picked here with Undo", async () => {
  setViewport(1440);
  const pickle = role({ role: "Dr. Pickle", name: "Dr. Pickle", library_item_id: 5, only_here: null, own_look_id: null, library_version: 2, description: "" });
  const settings = { look: "dr-pickle", video_model: null, image_model: null, aspect_ratio: "9:16", product_variants: {}, language: "en", video_models: [], image_models: [], shapes: ["9:16"], flavours: {}, presenter: null, presenter_now: "corner" };
  const calls = server(owner, [pickle], {
    "GET /projects/50/host": [200, { on: true, state: "none", pieces: [], credits: 0, presenter_id: 5, voice: "R8_CJRWYITM" }],
    "GET /projects/50/settings": [200, settings],
    "GET /brands/1/voices": [200, { voices: [{ id: 3, name: "Dr. Pickle (cloned)", kind: "cloned", stock_key: "R8_CJRWYITM", provider: "minimax", description: "Deep, fixed", sample_url: "/voices/samples/dr-pickle.mp3", preview_file_id: null, sample_file_id: null }], clone_credits: 29.18, clone_usd: 3 }],
    "POST /projects/50/settings": [200, { settings: { ...settings, presenter: "talks", presenter_now: "talks" }, was: { presenter: null } }],
  });
  open();
  const pres = await screen.findByRole("region", { name: "Presenter" });
  expect(within(pres).getByText("Talks over the B-roll for the whole video")).toBeInTheDocument();
  expect(within(pres).getByText("HeyGen, keyed over the B-roll", { selector: "dd" })).toBeInTheDocument();
  expect(await within(pres).findByText("Dr. Pickle (cloned) · MiniMax")).toBeInTheDocument();
  expect(within(pres).getByRole("button", { name: "Play Dr. Pickle (cloned)" })).toBeEnabled();
  expect(within(pres).getByText("Voices play here free. A new clone costs up to $3.00, once.")).toBeInTheDocument();
  const ways = within(pres).getByRole("radiogroup", { name: "How the presenter appears" });
  expect(within(ways).getAllByRole("radio").map((r) => r.textContent)).toEqual([
    "Talks to cameraHeyGen from one still, with B-roll laid over parts",
    "In a corner over the B-rollHeyGen, keyed over the B-roll",
    "Acts in the storyOmni: moves, acts, talks to others",
  ]);
  expect(within(ways).getByRole("radio", { name: /In a corner/ })).toBeChecked();
  await userEvent.click(within(ways).getByRole("radio", { name: /Talks to camera/ }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/settings")?.body).toEqual({ presenter: "talks" }));
  expect(await screen.findByText("Dr. Pickle now talks to camera.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((x) => x.key === "POST /projects/50/settings").at(-1)?.body).toEqual({ presenter: null, undo: true }));
});

test("P-09: on a phone each role is a short card; the one that needs a look keeps Library and Upload", async () => {
  setViewport(390);
  server(owner, [marcus, jade, chase]);
  open();
  const c = await screen.findByRole("region", { name: "Chase" });
  expect(within(c).getByText("Clips 2–4 wait for him")).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "Library" })).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "Upload" })).toBeInTheDocument();
  const j = screen.getByRole("region", { name: "Jade" });
  expect(within(j).getByText("Saved in fomo")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Marcus" })).getByText("Look for this video")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Marcus" })).queryByRole("button", { name: "Lock" })).toBeNull();
});

test("QA: every state has its press: a saved look waiting for its OK, a role-less character, a held drawing, an uploaded picture", async () => {
  setViewport(1440);
  const bo = role({ ref: "char:9", role: "Bo", name: "Bo", library_item_id: 9, slot_id: 7, sheet_status: "needs_approval", only_here: null, own_look_id: null, sheet_file_id: 75 });
  const extra = role({ ref: "char:10", role: "", name: "Barista", library_item_id: 10, slot_id: null, sheet_status: "none", only_here: null, own_look_id: null, sheet_file_id: null, description: "" });
  const held = role({ ref: "char:11", role: "Ana", name: "Ana", library_item_id: 11, slot_id: 8, sheet_status: "waiting_for_owner", drawing_job_id: 66, sheet_file_id: null });
  const photo = role({ ref: "char:12", role: "Kim", name: "Kim", library_item_id: 12, slot_id: 9, sheet_status: "none", sheet_file_id: null, photo_file_id: 88 });
  server(owner, [bo, extra, held, photo]);
  open();
  const b = await screen.findByRole("region", { name: "Bo" });
  expect(within(b).getByRole("link", { name: "Approve it in Cast & places" })).toHaveAttribute("href", "/b/1/library/characters/9");
  const x = screen.getByRole("region", { name: "Barista" });
  expect(within(x).getByRole("link", { name: "Make its look in Cast & places" })).toBeInTheDocument();
  expect(within(x).queryByRole("button", { name: /Pick|Upload|Make a look/ })).toBeNull(); // no role to cast here
  const h = screen.getByRole("region", { name: "Ana" });
  expect(within(h).getByText("Waiting for the owner")).toBeInTheDocument();
  expect(within(h).getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  const k = screen.getByRole("region", { name: "Kim" });
  expect(within(k).getByRole("img", { name: "Kim’s look" })).toHaveAttribute("src", "/api/files/88");
  expect(within(k).getByText("Your picture, for this video only. Its look is drawn from it.")).toBeInTheDocument();
});

test("QA: More on a role merges it into another (preview, then Undo) or deletes an own look it no longer uses", async () => {
  setViewport(1440);
  const swapped = role({ library_item_id: 21, own_look_id: 5, only_here: null, name: "Chase (rival)" });
  const calls = server(owner, [swapped, jade], { "DELETE /library/character/5": [204, {}], "POST /library/character/5/unarchive": [200, {}] });
  open();
  const m = await screen.findByRole("region", { name: "Marcus" });
  await userEvent.click(within(m).getByRole("button", { name: "More for Marcus" }));
  expect(screen.getByRole("menuitem", { name: "Merge into…" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete its own look" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "DELETE /library/character/5")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /library/character/5/unarchive")).toBe(true));
});

test("QA: until the server has the per-video presenter setting, the style's choice shows and can't be changed", async () => {
  setViewport(1440);
  const pickle = role({ role: "Dr. Pickle", name: "Dr. Pickle", library_item_id: 5 });
  server(owner, [pickle], {
    "GET /projects/50/host": [200, { on: true, state: "none", pieces: [], credits: 0, presenter_id: 5, voice: "Sarah" }],
    "GET /projects/50/settings": [200, { look: "ugc", video_model: null, image_model: null, aspect_ratio: "9:16", product_variants: {}, language: "en", video_models: [], image_models: [], shapes: ["9:16"], flavours: {} }],
  });
  open();
  const ways = await screen.findByRole("radiogroup", { name: "How the presenter appears" });
  expect(within(ways).getByRole("radio", { name: /In a corner/ })).toBeChecked(); // the project's own look (house) starts in the corner
  for (const r of within(ways).getAllByRole("radio")) expect(r).toBeDisabled();
  expect(await screen.findByText(/uses its style’s choice for now/)).toBeInTheDocument();
});

test("S-gaps-07 B: no OK on a card; the set is checked together and approved in one press, sending back what was seen", async () => {
  setViewport(1440);
  const set = gate([item("char:5", "Marcus"), item("slot:3", "Chase", { library_item_id: 30 })], { waiting: ["Marcus", "Chase"] });
  const chaseReady = role({ ref: "slot:3", role: "Chase", name: "Chase", library_item_id: 30, own_look_id: 30, slot_id: 3, sheet_status: "needs_approval" });
  const calls = server(owner, [role({ sheet_status: "needs_approval" }), chaseReady], { "GET /projects/50/cast": [200, set], "POST /projects/50/cast/approve": [200, gate(set.items, { state: "approved" })] });
  open();
  expect(await screen.findByText("Check the cast and places together.")).toBeInTheDocument();
  const m = screen.getByRole("region", { name: "Marcus" });
  expect(within(m).getByText("Ready to check")).toBeInTheDocument();
  expect(within(m).queryByRole("button", { name: "Approve" })).toBeNull(); // no per-card approval
  await userEvent.click(screen.getByRole("button", { name: "Approve cast & places" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/cast/approve")?.body).toEqual({ seen: { "char:5": "sig-char:5", "slot:3": "sig-slot:3" } }));
  expect(await screen.findByText("Cast and places approved. What waited for them carries on.")).toBeInTheDocument();
});

test("S-gaps-07 B: a change after the OK needs the combined OK again; the rest stay approved; clips with the old look wait for a choice", async () => {
  setViewport(1440);
  const chase2 = role({ ref: "char:30", role: "Chase", name: "Chase", library_item_id: 30, own_look_id: 30, slot_id: 3, sheet_status: "needs_approval", clip_ids: ["c2", "c3", "c4"] });
  const set = gate([item("char:5", "Marcus", { approval: "approved" }), item("char:30", "Chase", { approval: "changed", changes: ["look"], source: "uploaded", clip_ids: ["c2", "c3", "c4"] })], { approved_at: "2026-11-04T10:00:00Z", approved_by: "Reed", waiting: ["Chase"], update: { stills: [], clips: ["c2", "c3", "c4"], credits: 30, clips_credits: 26 } });
  server(owner, [marcus, chase2], { "GET /projects/50/cast": [200, set] });
  open();
  expect(await screen.findByText("Chase changed.")).toBeInTheDocument();
  expect(screen.getByText(/The other one stays approved, and clips without it carry on\./)).toBeInTheDocument();
  expect(screen.getByText("Needs you · 1 change")).toBeInTheDocument();
  const c = screen.getByRole("region", { name: "Chase" });
  expect(within(c).getByText("Changed · needs your OK")).toBeInTheDocument();
  expect(within(c).getByText("Uploaded for this video")).toBeInTheDocument();
  expect(within(c).getByText("Look changed")).toBeInTheDocument(); // what changed, by name (#1331's changes)
  const update = screen.getByRole("region", { name: "Made with an older look" });
  expect(within(update).getByText("Clips 2–4 were made with Chase’s old look")).toBeInTheDocument();
  expect(within(update).getByRole("button", { name: "Remake clips 2–4 with the new look · up to $2.68" })).toBeDisabled(); // after the OK
  expect(within(update).getByRole("button", { name: "Keep them" })).toBeInTheDocument();
});
test("Flow-QA S11: a look being drawn again reads as Drawing, never Approved, until it's checked", async () => {
  setViewport(1440);
  const set = gate([item("char:5", "Marcus", { approval: "approved", readiness: "drawing" })], { state: "approved", approved_at: "2026-11-04T10:00:00Z", approved_by: "Reed", not_ready: [{ ref: "char:5", name: "Marcus", why: "Marcus is still being drawn" }] });
  server(owner, [marcus], { "GET /projects/50/cast": [200, set] }); // its old sheet still reads approved
  open();
  const c = await screen.findByRole("region", { name: "Marcus" });
  expect(within(c).getByText("Drawing")).toBeInTheDocument();
  expect(within(c).queryByText("Approved")).toBeNull();
  expect(screen.getByText("Marcus is being drawn again")).toBeInTheDocument(); // the set, too
  expect(screen.queryByText("Approved")).toBeNull();
});
test("S5-02: the presenter's voice changes for this video only, from the voices with free samples, with Undo", async () => {
  setViewport(1440);
  const pickle = role({ role: "Dr. Pickle", name: "Dr. Pickle", library_item_id: 5 });
  const settings = { look: "dr-pickle", video_model: null, image_model: null, aspect_ratio: "9:16", product_variants: {}, language: "en", video_models: [], image_models: [], shapes: ["9:16"], flavours: {}, presenter: null, presenter_now: "corner", voice: "voice:3" };
  const voice = (id: number | null, name: string, key: string | null, provider: string) => ({ id, name, kind: id ? "cloned" : "stock", stock_key: key, provider, description: "", sample_url: `/voices/samples/${name}.mp3`, preview_file_id: null, sample_file_id: null });
  const calls = server(owner, [pickle], {
    "GET /projects/50/host": [200, { on: true, state: "none", pieces: [], credits: 0, presenter_id: 5, voice: "R8_CJRWYITM" }],
    "GET /projects/50/settings": [200, settings],
    "GET /brands/1/voices": [200, { voices: [voice(3, "Dr. Pickle (cloned)", null, "minimax"), voice(null, "Roger", "Roger", "elevenlabs")], clone_credits: 29.18, clone_usd: 3 }],
    "POST /projects/50/settings": [200, { settings: { ...settings, voice: "stock:Roger" }, was: { voice: "voice:3" } }],
  });
  open();
  const pres = await screen.findByRole("region", { name: "Presenter" });
  expect(await within(pres).findByText(/Dr\. Pickle \(cloned\) · MiniMax/)).toBeInTheDocument();
  await userEvent.click(within(pres).getByRole("button", { name: "Change the voice" }));
  const voices = within(pres).getByRole("radiogroup", { name: "The narrator’s voice" });
  expect(within(voices).getByRole("radio", { name: "Dr. Pickle (cloned)" })).toBeChecked();
  await userEvent.click(within(voices).getByRole("radio", { name: "Roger" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/settings")?.body).toEqual({ voice: "stock:Roger" }));
  expect(await screen.findByText("The narrator is now Roger.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((x) => x.key === "POST /projects/50/settings").at(-1)?.body).toEqual({ voice: "voice:3", undo: true }));
});

test("S5-02: a described voice is said in its words and the app voice that reads it", async () => {
  setViewport(1440);
  const pickle = role({ role: "Dr. Pickle", name: "Dr. Pickle", library_item_id: 5 });
  const settings = { look: "dr-pickle", video_model: null, image_model: null, aspect_ratio: "9:16", product_variants: {}, language: "en", video_models: [], image_models: [], shapes: ["9:16"], flavours: {}, presenter: null, presenter_now: "corner", voice: "voice:9" };
  const dana = { id: 9, name: "Dana", kind: "described", uses: "Graceful Lady", stock_key: null, provider: "minimax", description: "late 40s, tired, warm", sample_url: "/voices/samples/English_Graceful_Lady.mp3", preview_file_id: null, sample_file_id: null };
  const lady = { ...dana, id: null, name: "Graceful Lady", kind: "stock", uses: null, stock_key: "English_Graceful_Lady", description: "Older woman" };
  server(owner, [pickle], {
    "GET /projects/50/host": [200, { on: true, state: "none", pieces: [], credits: 0, presenter_id: 5, voice: "voice:9" }],
    "GET /projects/50/settings": [200, settings],
    "GET /brands/1/voices": [200, { voices: [dana, lady], clone_credits: 29.18, clone_usd: 3 }],
  });
  open();
  const pres = await screen.findByRole("region", { name: "Presenter" });
  await userEvent.click(await within(pres).findByRole("button", { name: "Change the voice" }));
  const voices = within(pres).getByRole("radiogroup", { name: "The narrator’s voice" });
  expect(within(voices).getByRole("radio", { name: "Dana" })).toBeChecked();
  expect(within(voices).getByText("Described: “late 40s, tired, warm” · Graceful Lady’s voice")).toBeInTheDocument();
  expect(within(voices).getByRole("radio", { name: "Graceful Lady" })).not.toBeChecked();
});

test("S-gaps-07 B: who made a look and its last revision, what the previews cost so far, and Keep them on clips made with an old look", async () => {
  setViewport(1440);
  const mom = role({ ref: "char:31", role: "Mom", name: "Mom", library_item_id: 31, own_look_id: 31, slot_id: 6, sheet_status: "needs_approval", clip_ids: ["c4"] });
  const set = gate(
    [item("char:5", "Marcus", { approval: "approved" }), item("char:31", "Mom", { made_by: "director", made_at: "2026-11-04T09:06:00", revised_by: "Reed", revised_at: "2026-11-04T09:21:00", revised_why: "warmer, a bit older", was_preview_file_id: 77, clip_ids: ["c4"] })],
    { waiting: ["Mom"], previews: { credits: 4.7, usd: 0.48, budget_credits: 189, budget_usd: 19.4 }, update: { stills: [], clips: ["c4"], credits: 9, clips_credits: 9, kept_items: [] } },
  );
  const calls = server(owner, [marcus, mom], { "GET /projects/50/cast": [200, set], "POST /projects/50/cast/keep": [200, gate(set.items, { update: { stills: [], clips: [], credits: 0, clips_credits: 0, kept_items: [{ kind: "clip", id: "c4", by: "Reed", at: "2026-11-04T09:30:00" }] } })] });
  open();
  const m = await screen.findByRole("region", { name: "Mom" });
  const local = (utc: string) => new Date(utc).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }); // the server's UTC, shown like the chat
  expect(within(m).getByText(`Made by the director in the chat · ${local("2026-11-04T09:06:00Z")}`)).toBeInTheDocument();
  expect(within(m).getByText(`Revised ${local("2026-11-04T09:21:00Z")} after your note`)).toBeInTheDocument();
  expect(within(m).getByRole("img", { name: "The look before" })).toHaveAttribute("src", "/api/files/77");
  expect(screen.getByText(/Previews so far: \$0\.48 of the approved budget\./)).toBeInTheDocument();
  const update = screen.getByRole("region", { name: "Made with an older look" });
  await userEvent.click(within(update).getByRole("button", { name: "Keep them" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/cast/keep")?.body).toEqual({}));
});

test("a voice change on an approved character is named, with its sample, and needs the combined OK again; the rest stay approved", async () => {
  setViewport(1440);
  const set = gate([item("char:5", "Marcus", { approval: "approved" }), item("char:30", "Chase", { approval: "changed", changes: ["voice"], voice: { name: "Roger", sample_url: "/voices/samples/Roger.mp3" }, was_voice: { name: "Sarah", sample_url: null } })], { approved_at: "2026-11-04T10:00:00Z", waiting: ["Chase"] });
  const chase2 = role({ ref: "char:30", role: "Chase", name: "Chase", library_item_id: 30, own_look_id: 30, slot_id: 3 });
  server(owner, [marcus, chase2], { "GET /projects/50/cast": [200, set] });
  open();
  const c = await screen.findByRole("region", { name: "Chase" });
  expect(within(c).getByText(/Voice changed: Sarah → Roger/)).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "Play Roger’s voice" })).toBeInTheDocument();
  expect(within(c).getByText("Changed · needs your OK")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Marcus" })).getByText("Approved")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve cast & places" })).toBeEnabled();
});

test("Reed 8: the presenter is made again with its scope and up-to price first, and the one there stays until then", async () => {
  setViewport(1440);
  const pickle = role({ role: "Dr. Pickle", name: "Dr. Pickle", library_item_id: 5 });
  const piece = (number: number, credits: number) => ({ number, start: 0, end: 4, state: "ready", file_id: 900 + number, earlier: [], error: "", credits });
  const calls = server(owner, [pickle], {
    "GET /projects/50/host": [200, { on: true, state: "ready", pieces: [piece(0, 9), piece(1, 3), piece(2, 3)], credits: 0, presenter_id: 5, voice: "Sarah" }],
    "POST /projects/50/host/0": [201, { on: true, state: "making", pieces: [], credits: 0, presenter_id: 5, voice: "Sarah" }],
  });
  open();
  const pres = await screen.findByRole("region", { name: "Presenter" });
  await userEvent.click(within(pres).getByRole("button", { name: "Make the presenter again…" }));
  expect(within(pres).getByText(/the still, then all 2 pieces of the narration from it\. The presenter you have now stays until the new one is made/)).toBeInTheDocument();
  await userEvent.click(within(pres).getByRole("button", { name: "Make it again · up to $0.93" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/host/0")).toBe(true));
});

test("Reed 8: the earlier presenter comes back free, with Undo", async () => {
  setViewport(1440);
  const pickle = role({ role: "Dr. Pickle", name: "Dr. Pickle", library_item_id: 5 });
  const piece = (number: number) => ({ number, start: 0, end: 4, state: "ready", file_id: 900 + number, earlier: [800 + number], error: "", credits: 3 });
  const out = { on: true, state: "ready", pieces: [piece(0), piece(1)], credits: 0, presenter_id: 5, voice: "Sarah" };
  const calls = server(owner, [pickle], { "GET /projects/50/host": [200, out], "POST /projects/50/host/back": [200, out] });
  open();
  const pres = await screen.findByRole("region", { name: "Presenter" });
  await userEvent.click(within(pres).getByRole("button", { name: "Use the earlier presenter · free" }));
  await vi.waitFor(() => expect(calls.filter((x) => x.key === "POST /projects/50/host/back")).toHaveLength(1));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((x) => x.key === "POST /projects/50/host/back")).toHaveLength(2));
});

test("only the video's maker or the owner approves the cast and places; others see the state, read only", async () => {
  setViewport(1440);
  const set = gate([item("char:5", "Marcus")], { waiting: ["Marcus"], can_approve: false });
  server(editor, [role({ sheet_status: "needs_approval" })], { "GET /projects/50/cast": [200, set] });
  open();
  expect(await screen.findByText("Check the cast and places together.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve cast & places" })).toBeNull();
  expect(screen.getByText("Whoever made this video, or the owner, approves the cast and places.")).toBeInTheDocument();
});

test("QA: without the checkpoint on the server, a place with no look offers no presses that would fail", async () => {
  setViewport(1440);
  const pent = { kind: "place", ref: "place:41", role: "", library_item_id: 41, name: "The penthouse", locked: false, sheet_status: "none", ready: false, slot_id: null, description: "", shots: 1, clip_ids: ["c3"], sheet_file_id: null };
  server(owner, [marcus, pent]); // GET /cast isn't faked: a server without #1331
  open();
  const p = await screen.findByRole("region", { name: "The penthouse" });
  expect(within(p).queryByRole("button", { name: /library|Upload|Make one/ })).toBeNull();
  expect(within(p).getByText(/made with the cast and places/)).toBeInTheDocument();
});

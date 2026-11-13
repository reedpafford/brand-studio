import type { components } from "../api/schema";
import { cutOut } from "./cut";
import { owner } from "./people";

/** One video (366, "Three men at Target", nine clips in two scenes) as the server answers it, in each state the new
 *  look's video page (studio/Video.tsx) can show: the plan waiting for the press, the plan being updated for a note,
 *  being made, stopped, needing him (a provider account empty, a step that failed twice), delivered (a time card on the
 *  timeline, a clip left out of the cut, a flagged take, edits waiting for the next cut), a round after a note, the
 *  cast waiting for its own OK, each kind of question, archived, and one made by the earlier director. Each is a whole
 *  fake server: pass it to `fakeServer`. The shapes are the schema's own. */
type S = components["schemas"];
export type Routes = Record<string, [number, unknown]>;

const SCRIPT = [
  "[Dusk in a Target parking lot. A siren is screaming and a white strobe flashes across the lot.]",
  "STROLLER MOM (on the phone): Two men just tried to abduct a girl in the Target parking lot!",
  "[A teenage boy who collects the carts runs after the van with his phone up.]",
  "CART KID: I got the plate! I got it!",
  "[A tall girl in a volleyball sweatshirt stands over a carton of broken eggs.]",
  "STROLLER MOM (on the phone): She's okay. She's standing right here.",
  "[Twenty minutes earlier. Inside Target, Paige takes a carton of eggs off the shelf.]",
  "PAIGE (V.O.): Weird. But whatever.",
  "PAIGE (V.O.): Wait. Nobody's buying anything.",
].join("\n\n");
export const LEFT_OUT = "This same prompt for clip 2 was blocked by the service's safety filter (it said: sensitive content) before, so it would be again. Change the prompt first. Nothing was charged.";
const TREATMENT = { hook: "A siren, a white strobe, a van pulling away with its door open.", logline: "A girl was nearly taken buying eggs, and nobody in the store noticed the three men who were buying nothing.", why_it_holds: "It starts with the outcome, so every quiet aisle after it is a clue the viewer reads before she does.", beats: [] };

// The plan: nine clips, one shot each. [seconds, scene, speaker, line, what the camera sees]
const CLIPS: [number, number, string | null, string | null, string][] = [
  [8, 1, "STROLLER MOM", "Two men just tried to abduct a girl in the Target parking lot!", "She runs with the stroller, phone to her ear, the van pulling out behind her."],
  [4, 1, "CART KID", "I got the plate! I got it!", "He runs after the van, phone held high."],
  [4, 1, null, null, "The alarm still screaming in her hand, eggs broken on the asphalt."],
  [7, 1, "STROLLER MOM", "She's okay. She's standing right here.", "Paige frozen, the woman beside her, dusk behind."],
  [7, 2, "PAIGE", "Weird. But whatever.", "Over her shoulder down the aisle. He stands with no cart, hands in his pockets."],
  [6, 2, null, null, "She turns into the next aisle. Same sweatsuit, same boots."],
  [8, 2, "PAIGE", "Construction guys, probably.", "Paige at the freezer doors; the third man reflected in the glass."],
  [8, 2, null, null, "From the end of the aisle: one walks past, then another."],
  [8, 2, "PAIGE", "Wait. Nobody's buying anything.", "A slow push in to a close-up as it lands on her."],
];
const SCENES = ["The lot, after", "The store, twenty minutes earlier"];
/** What the plan calls each clip, and the one time card (on black before clip 5). */
const NAMES = ["The lot, seconds after", "He got the plate", "Eggs on the asphalt", "She’s okay", "Three men, no carts", "The next aisle", "The freezer doors", "One, then another", "Nobody’s buying"];
const CARD = "TWENTY MINUTES EARLIER";
const shot = (n: number): S["Shot"] => ({ id: `${CLIPS[n][1]}.${n + 1}`, script_lines: [], speaker: CLIPS[n][2], line: CLIPS[n][3], action: CLIPS[n][4], reaction: null, camera: "Handheld.", seconds: CLIPS[n][0], character_ids: [], place_id: null, moment: null, screen_ids: [] });
const breakdown: S["Breakdown"] = {
  hook: TREATMENT.hook,
  scenes: SCENES.map((heading, s) => ({ id: s + 1, heading, look: "", shots: CLIPS.flatMap((c, n) => (c[1] === s + 1 ? [shot(n)] : [])) })),
  clips: CLIPS.map((c, n) => ({ id: `c${n + 1}`, shot_ids: [shot(n).id], seconds: c[0], seam: "" })),
};

/** One row of GET …/clips: `made` has its take; `left` is why it was left out of the cut. */
const clip = (n: number, made: boolean, left: string | null = null): S["ProjectClipOut"] => ({
  id: 500 + n, clip_id: `c${n}`, seconds: CLIPS[n - 1][0], prompt: "", references: [], problems: [], kept: [], file_id: made ? 200 + n : null,
  takes: made ? [{ id: 100 + n, number: 1, file_id: 200 + n, created_at: "2026-11-13T09:20:00", verdict: "", mutes: [] }] : [],
  picked_take_id: made ? 100 + n : null, approved: made, prompt_ok: true, take_credits: 5, stale: false, take_stale: false, inserts: [], change: null, free_fix_used: false, left_out: left, versions: [], spent: 0, stills: 0, name: NAMES[n - 1], card: n === 5 ? CARD : "", card_before: n === 5, opening: 0, sound: { state: "none", how: "", asked: "", error: "", credits: 0.5 },
});
const cell = (n: number, state: S["ClipCellOut"]["state"]): S["ClipCellOut"] => ({ clip_id: `c${n}`, number: String(n), scene: CLIPS[n - 1][1], label: CLIPS[n - 1][4].split(". ")[0].replace(/\.$/, ""), seconds: CLIPS[n - 1][0], model: "Seedance", state, frame_file_id: state === "done" ? 300 + n : null, take_id: state === "done" ? 100 + n : null, note: "", percent: null, minutes_left: state === "making" ? 1 : null, credits: null, changed: false, watched: true, found: false });
const step = (key: string, state: S["RunStepOut"]["state"], text: string, sub = ""): S["RunStepOut"] => ({ key, state, text, sub });
/** GET …/director/progress, with each clip's state in order. */
function progress(states: S["ClipCellOut"]["state"][], o: Partial<S["ProgressOut"]>): S["ProgressOut"] {
  const cells = states.map((s, i) => cell(i + 1, s));
  const made = cells.filter((c) => c.state === "done").length;
  return {
    run: "r1", status: "working", title: "Making the clips", sub: `${made} of 9 · scene 2 of 2`, tone: "now", started_at: "2026-11-13T09:19:00", ended_at: null, clips: 9, made, redone: 0, scene_at: 2,
    scenes: SCENES.map((name, s) => ({ id: s + 1, name, total: cells.filter((c) => c.scene === s + 1).length, done: cells.filter((c) => c.scene === s + 1 && c.state === "done").length, clips: cells.filter((c) => c.scene === s + 1) })),
    counts: { all: 9, needs_you: 0, flagged: 0, redone: 0 }, minutes_left: null, steps: [], spent: 24.6, up_to: 60, spent_usd: 2.46, actual_usd: 2.46, expected_usd: 4.87, unreported: false, cost: "$2.46 on this run", changed: [], stopped: null, stops: [], failed: null, ...o,
  };
}
const READ = step("read", "done", "Read the script, the Movie guide and Palace Guard’s brand kit");
const PLAN = step("plan", "done", "Treatment and plan: 2 scenes, 9 clips, about 60 s");
const CAST = step("cast", "done", "Cast and places: Paige, the man in gray, the woman with the stroller, the cart kid");

const person = (ref: string, name: string, file: number, o: Partial<S["CastItemOut"]> = {}): S["CastItemOut"] => ({ ref, kind: "character", name, library_item_id: null, version: null, source: "video", preview_file_id: file, readiness: "ready", approval: "approved", sig: "s", clip_ids: ["c1", "c4"], changes: [], ...o });
const CAST_ITEMS = [
  person("char:11", "Paige", 401, { source: "library", library_item_id: 11, clip_ids: ["c3", "c4", "c5", "c6", "c7", "c8", "c9"], voice: { name: "Light and clear, a little dry", sample_url: "/voices/11/sample" } }),
  person("char:12", "The man in gray", 402, { clip_ids: ["c5", "c6", "c7", "c8"], look_fit: { seen: "a man in his twenties", problem: "the script says he is in his forties" } }),
  person("char:13", "The woman with the stroller", 403, { voice: { name: "Fast and breathless", sample_url: null } }),
  person("slot:4", "The cart kid", 404, { preview_file_id: null, readiness: "drawing", clip_ids: ["c2"] }),
  person("place:21", "Target parking lot", 411, { kind: "place", clip_ids: ["c1", "c2", "c3", "c4"] }),
  person("place:22", "Target aisles", 412, { kind: "place", clip_ids: ["c5", "c6", "c7", "c8", "c9"] }),
];
const asset = (kind: string, ref: string, name: string, description: string, file_id: number | null = null) => ({ kind, ref, role: "", library_item_id: null, name, locked: false, sheet_status: "approved", ready: true, description, shots: 1, file_id, declined: false, library_deleted: false, clip_ids: [], script_unlock: false });
const ASSETS = [asset("character", "char:11", "Paige", "18, tall, volleyball sweatshirt"), asset("character", "char:12", "The man in gray", "Forties, gray sweatsuit, work boots"), asset("place", "place:21", "Target parking lot", "Dusk, one light half out"), asset("product", "screen:5", "Protector alarm", "", 450)];

const ask = (id: number, o: Partial<S["AskOut"]>): S["AskOut"] => ({ id, project_id: 366, kind: "start", topic: "", subject: "", question: "", why: "", state: "open", by_owner: false, saved_in: "", saved: [], choices: [], clone_to: "", options: [], audition: [], voice_name: "", voice_saved: false, audition_failed: false, other_voices: [], answered_by: "", closed: "", can: [], created_at: "2026-11-13T09:19:00", ...o });
const START = ask(7, { question: "Make it for about $4.87?", why: "Nothing is filmed until you say so.", can: ["make_it", "decline"], money: { up_to: { credits: 48.7, usd: 4.87 }, expected: true, clips: [], making: CLIPS.map((c, n) => ({ clip: String(n + 1), seconds: c[0], price: { credits: c[0] * 0.66, usd: c[0] * 0.066 }, opening: 0 })), sent_at: "2026-11-13T09:19:00", held: "", since: "", updating: false, carry: false, what: "", over: "the budget" } });
const STARTED = { ...START, state: "answered", answered_by: "Reed", answered_at: "2026-11-13T09:20:00", can: [] };
const QUESTION = ask(8, { kind: "cast", topic: "The woman with the stroller", subject: "the woman with the stroller", question: "Who plays the woman with the stroller?", why: "She opens the hook and has two lines. Use someone saved in Palace Guard, or make someone new.", saved_in: "Saved in Palace Guard", saved: [{ id: "char:31", name: "Dana", note: "", used_in: 2 }, { id: "char:32", name: "The store manager", note: "", used_in: 1 }], can: ["saved", "upload", "generate", "reply"], created_at: "2026-11-13T09:21:00" });

type Item = Partial<S["ThreadItem"]> & { id: string };
const said = (kind: "message" | "move" | "ask", at: string, o: Item) => ({ kind, at: `2026-11-13T${at}:00`, who: kind === "message" ? "Reed" : "Director", text: "", status: kind === "move" ? "done" : null, why: "", files: [], ...o });
const NOTE: S["DeliveryNoteOut"] = { made: "A 55-second cut in eight clips, every line as written.", redid: [{ at: 12, clip: "c4", text: "Her mouth moved on a line that is voice-over. I made it again with her mouth closed." }], unsure: "", open: [`Clip 2 couldn’t be made, so the cut is without it: ${LEFT_OUT}`], needs: "Watch it through. Say if you want clip 2 made another way.", cost: "$4.61 so far", spent: 46.1, up_to: 60, spent_usd: 4.61, cut: 1, seconds: 55, clips: 8 };

const status = (kind: string, words: string, reason: string | null = null) => ({ kind, words, reason, at: null, made: 0, total: 9 });
const piece = (id: string, n: number, start: number, end: number, card: string | null = null): S["PieceOut"] => ({ id, clip_id: `c${n}`, take_id: card ? null : 100 + n, file_id: card ? null : 200 + n, poster_file_id: card ? null : 300 + n, source: card ? "Card" : `Clip ${n}`, start, end, in_point: 0, said: card ? "" : (CLIPS[n - 1][3] ?? ""), edited: false, director: false, changed: false, card });
/** The delivered cut: clip 2 has no piece, and "TWENTY MINUTES EARLIER" is a card on black before clip 5. */
const PIECES = [piece("c1", 1, 0, 8), piece("c3", 3, 8, 12), piece("c4", 4, 12, 19), piece("c5.card", 5, 19, 21.6, CARD), piece("c5", 5, 21.6, 28.6), piece("c6", 6, 28.6, 34.6), piece("c7", 7, 34.6, 42.6), piece("c8", 8, 42.6, 50.6), piece("c9", 9, 50.6, 58.6)];
const cut = (o: Partial<S["TimelineOut"]> = {}, file: number | null = null) => cutOut({ number: file && 1, file_id: file, versions: file ? [{ number: 1, file_id: file, made_at: "2026-11-13T09:33:00" }] : [], timeline: { ...cutOut().timeline, mode: "takes", presenter: null, voice: null, music: null, words: [], sfx: [], pieces: [], length: 0, captions: true, cards: true, ...o } });

/** The whole fake server for one state of the video. */
function video(o: { status: object; spent: number; moves?: object[]; thread?: object[]; progress: S["ProgressOut"]; asks: S["AskOut"][]; clips: S["ProjectClipOut"][]; cut: S["CutOut"]; expected?: number; sent?: string; director?: Partial<S["DirectorOut"]>; cast?: Partial<S["CastOut"]>; project?: object }): Routes {
  const idea = { id: 366, title: "Three men at Target", folder_id: null, status: o.status, still_file_id: null, look: "movie", style: "Movie", seconds: 60, made_by: null, created_at: "2026-11-13T09:14:00", updated_at: "2026-11-13T09:14:00", cost: null, can_manage: true, from_script: false };
  const moves = [said("message", "09:14", { id: "m1", text: SCRIPT }), said("move", "09:17", { id: "t1", text: "Here’s how I’ll make it.", treatment: TREATMENT }), said("move", "09:19", { id: "t2", text: "Making the clips." }), ...(o.moves ?? [])];
  return {
    "GET /auth/me": [200, owner],
    "GET /brands": [200, [{ id: 1, name: "Palace Guard", colours: ["#ef8a3c"] }]],
    "GET /workspace": [200, { id: 1, name: "Brand Studio" }],
    "GET /brands/1/tree": [200, { folders: [], unsorted: { id: null, parent_id: null, name: "Unsorted", count: 1, can_manage: false, ideas: [], more: 0, folders: [] } }],
    "GET /brands/1/ideas": [200, { total: 1, counts: { all: 1, needs_you: 0, working: 0, delivered: 0 }, archived: 0, folders_inside: 0, makers: [], ideas: [idea] }],
    "GET /projects/366": [200, { id: 366, brand_id: 1, name: "Three men at Target", freestyle_id: 9, aspect_ratio: "9:16", look: "movie", engine: "one_pass", credits_used: o.spent * 10, budget_credits: 600, created_by_id: 1, created_by_name: "Reed", folder_id: null, product_variants: {}, plan_status: "none", kind: "story", ...o.project }],
    "GET /freestyles/9": [200, { id: 9, title: "Three men at Target", type: "dialogue", look: "movie", shape: "9:16", brand_id: 1, status: o.sent ?? "working", created_by_name: "Reed", created_at: "2026-11-13T09:14:00", credits: 0, file_id: null, project_id: 366, waiting: [], thread: moves }],
    "GET /projects/366/director": [200, { status: "running", ended: "", turns: [], credits: 0, spent_usd: o.spent, start_blocked: "", thread: [said("move", "09:19", { id: "t2", run: "r1" }), ...(o.thread ?? [])], unread: 0, run_price: 0, spent: 0, started: true, waiting: [], ...o.director }],
    "GET /projects/366/idea": [200, { title: "Three men at Target", status: o.status, spent: { credits: o.spent * 10, usd: o.spent }, up_to: null, budget: null, expected: o.expected ? { credits: o.expected * 10, usd: o.expected } : null, actual: true, unreported: false, folder: null, format: "Dialogue", style: "Movie", seconds: 60, song: false, usd_per_credit: 0.1 }],
    "GET /projects/366/director/progress": [200, o.progress],
    "GET /projects/366/director/thinking": [200, { thinking: "", written: [] }],
    "GET /projects/366/asks": [200, o.asks],
    "GET /projects/366/clips": [200, o.clips],
    "GET /projects/366/breakdown": [200, { id: 1, script_version: 1, source: "director", breakdown, problems: [], kept: [], stale: false, changed_shots: [], fixes: [], fixed: [], unknown_names: {}, older_plan: false, director_run: true }],
    "GET /projects/366/cut": [200, o.cut],
    "GET /projects/366/cast": [200, { state: "approved", approved_by: "Reed", approved_at: "2026-11-13T09:20:00", asked: false, can_approve: true, items: CAST_ITEMS, waiting: [], not_ready: [], paused_clips: [], update: { stills: [], clips: [], credits: 0 }, previews: { credits: 0, usd: 0, budget_credits: 0, budget_usd: 0 }, ...o.cast }],
    "GET /projects/366/assets": [200, ASSETS],
    "GET /usage/videos/366": [200, { project_id: 366, brand_id: 1, brand: "Palace Guard", title: "Three men at Target", spend_usd: o.spent, spend_estimated: false, providers: [], kinds: [{ name: "Claude’s thinking", usd: 0.61, estimated: false }, { name: "Looks", usd: 0.3, estimated: false }, { name: "Takes", usd: Math.max(0, o.spent - 0.91), estimated: false }], last_at: "2026-11-13T09:33:00", unreported: false, runs: [] }],
  };
}

const todo = Array<S["ClipCellOut"]["state"]>(9).fill("todo");
/** One move the director has made: with it, a run whose status is running is going. */
const TURN: S["TurnOut"] = { turn: 1, tool: "make_take", why: "", result: "", status: "done", created_at: "2026-11-13T09:20:00" };
/** The plan is written and drawn, and the start card waits for Make it: nothing is filmed. */
export const planWaiting = video({ status: status("needs_you", "Needs you", "Start it"), spent: 0.91, expected: 4.87, sent: "waiting", director: { make_it: 7 }, thread: [said("ask", "09:19", { id: "a7", ask_id: 7 })], asks: [START], clips: CLIPS.map((_, n) => clip(n + 1, false)), cut: cut(), progress: progress(todo, { status: "waiting", title: "Ready to make", sub: "9 clips · about 60 s", tone: "wait", spent_usd: 0.91, actual_usd: 0.91, cost: "$0.91 on this run", steps: [READ, PLAN, CAST, step("takes", "todo", "Making takes: 0 of 9"), step("cut", "todo", "Watch and listen to the whole cut, then deliver")] }) });

/** Four of nine clips are made, the fifth is being made, and a note he sent while it films has its reply. */
export const beingMade = video({
  status: status("working", "Working", "4 of 9"), spent: 2.46, expected: 4.87, director: { turns: [TURN] },
  moves: [said("move", "09:25", { id: "t4", text: "Got it. Clip 6 isn’t filmed yet, so it is made that way. No extra cost." })],
  thread: [said("ask", "09:19", { id: "a7", ask_id: 7 }), said("message", "09:24", { id: "n1", text: "Add shoppers in the store, going about their evening." })],
  asks: [STARTED], clips: CLIPS.map((_, n) => clip(n + 1, n < 4)), cut: cut(),
  progress: progress(["done", "done", "done", "done", "making", ...todo.slice(5)], { minutes_left: 4, steps: [READ, PLAN, CAST, step("takes", "now", "Making takes: 4 of 9", "Clip 5 · scene 2 · 7 s · about 1 min"), step("cut", "todo", "Watch and listen to the whole cut, then deliver")] }),
});

/** Delivered: eight clips in the cut, clip 2 left out of it, and a time card before clip 5. */
export const delivered = video({
  status: status("delivered", "Delivered"), spent: 4.61, sent: "delivered", director: { status: "delivered" },
  moves: [said("move", "09:33", { id: "t3", text: "Here’s the cut." })],
  thread: [said("ask", "09:19", { id: "a7", ask_id: 7 }), said("move", "09:33", { id: "t3", note: NOTE })],
  asks: [STARTED], clips: CLIPS.map((_, n) => clip(n + 1, n !== 1, n === 1 ? LEFT_OUT : null)), cut: cut({ pieces: PIECES, length: 58.6 }, 90),
  progress: progress(["done", "todo", ...Array<"done">(7).fill("done")], { status: "delivered", title: "Delivered in 14 min", sub: "8 clips", tone: "done", ended_at: "2026-11-13T09:33:00", spent_usd: 4.61, actual_usd: 4.61, cost: "$4.61 on this run", steps: [READ, PLAN, CAST, step("takes", "done", "Takes: 8 made"), step("cut", "done", "Watch and listen to the whole cut, then deliver")] }),
});

/** The director stopped on a question only he can answer: who plays the woman with the stroller. */
export const question = video({ status: status("needs_you", "Needs you", "Who plays the woman with the stroller?"), spent: 0.52, director: { turns: [TURN], waiting: [{ id: 8, topic: "The woman with the stroller", question: QUESTION.question }] }, thread: [said("ask", "09:21", { id: "a8", ask_id: 8 })], asks: [QUESTION], clips: [], cut: cut(), progress: progress(todo, { status: "waiting", title: "Waiting for you", sub: "1 question", tone: "wait", spent_usd: 0.52, actual_usd: 0.52, cost: "$0.52 on this run", steps: [READ, PLAN, step("cast", "wait", "Cast and places", "1 question waiting"), step("takes", "todo", "Making takes: 0 of 9"), step("cut", "todo", "Watch and listen to the whole cut, then deliver")] }) });

// ── The states that act (stage 3). Each is one of the four above with some of its answers changed. ──
const read = <T>(base: Routes, path: string) => base[`GET /projects/366${path}`][1] as T;
/** `base` with these reads of the video changed ("" is the video itself), and its send's status when given. */
const over = (base: Routes, o: Record<string, unknown>, sent?: string): Routes => ({
  ...base,
  ...Object.fromEntries(Object.entries(o).map(([path, body]) => [`GET /projects/366${path}`, [200, body]])),
  ...(sent ? { "GET /freestyles/9": [200, { ...(base["GET /freestyles/9"][1] as object), status: sent }] } : {}),
});
const runOf = (base: Routes, o: Partial<S["DirectorOut"]>) => ({ ...read<S["DirectorOut"]>(base, "/director"), ...o });
const headOf = (base: Routes, s: object) => ({ ...read<object>(base, "/idea"), status: s });
const fourMade = ["done", "done", "done", "done", ...todo.slice(4)] as S["ClipCellOut"]["state"][];
const stepsAt = (takes: S["RunStepOut"]["state"]) => [READ, PLAN, CAST, step("takes", takes, "Making takes: 4 of 9"), step("cut", "todo", "Watch and listen to the whole cut, then deliver")];

/** A note he sent while the start card waited is being read into the plan: the card stays, without its press. */
export const planUpdating = over(planWaiting, { "/asks": [{ ...START, can: ["decline"], money: { ...START.money!, updating: true } }] });

/** He stopped it with four clips made: Carry on at the rest of the run's price, or Start the plan again. */
export const stopped = over(
  beingMade,
  { "/director": runOf(beingMade, { status: "stopped" }), "/idea": headOf(beingMade, status("stopped", "Stopped")), "/director/progress": progress(fourMade, { status: "stopped", title: "Stopped", sub: "4 of 9 clips made", tone: "stop", ended_at: "2026-11-13T09:26:00", steps: stepsAt("todo"), stopped: { by: "Reed", at: "2026-11-13T09:26:00", made: 4, total: 9, carry_on: "$2.41", free: false } }) },
  "stopped",
);

const needs = (failed: S["RunFailedOut"]) => over(beingMade, { "/director": runOf(beingMade, { status: "failed" }), "/idea": headOf(beingMade, status("needs_fix", "Needs you", failed.title)), "/director/progress": progress(fourMade, { status: "needs_fix", title: failed.title, sub: "4 of 9 clips made", tone: "bad", ended_at: "2026-11-13T09:26:00", steps: stepsAt("bad"), failed }) }, "failed");
export const KIE_EMPTY = "KIE is out of credits, so this wasn't started and nothing was charged. Top up KIE, then try again.";
/** A provider's account is empty: nothing more can be made until it is topped up; then Carry on. */
export const needsService = needs({ title: "KIE is out of credits", why: KIE_EMPTY, offer: "", clip: null, fixes: [{ kind: "carry_on", label: "Carry on", price: "$2.41", problem: "" }] });
/** A step failed twice: try that clip again, or carry on without it. */
export const broke = needs({ title: "Clip 5 couldn’t be made", why: "The service couldn't finish this twice running. Nothing was charged.", offer: "", clip: 505, fixes: [{ kind: "again", label: "Try again", price: "$0.70", problem: "" }, { kind: "carry_on", label: "Carry on without it", price: null, problem: "" }] });

const ROUND = ask(9, { question: "Make it for about $0.99?", why: "Nothing is filmed until you say so.", can: ["make_it", "decline"], created_at: "2026-11-13T09:42:00", money: { ...START.money!, up_to: { credits: 9.9, usd: 0.99 }, making: [{ clip: "4", seconds: 7, price: { credits: 4.6, usd: 0.46 }, opening: 0 }, { clip: "9", seconds: 8, price: { credits: 5.3, usd: 0.53 }, opening: 0 }] } });
const AFTER = read<S["DirectorOut"]>(delivered, "/director").thread;
export const HIS_NOTE = "Clip 4: she should look at the van, not at the camera. And hold longer on Paige at the end.";
/** After the delivery he sent a note: it came back as a round, the two clips it changes, each with its price. */
export const round2 = over(delivered, { "/asks": [STARTED, ROUND], "/idea": headOf(delivered, status("needs_you", "Needs you", "Start it")), "/director": runOf(delivered, { status: "running", make_it: 9, thread: [...AFTER, said("message", "09:40", { id: "n2", text: HIS_NOTE }), said("ask", "09:42", { id: "a9", ask_id: 9 })] as S["ThreadItem"][] }) }, "waiting");

/** Something changed the cast after the plan was approved: the cast waits for its own OK, and the look check objects. */
export const castChanged = over(beingMade, { "/cast": { ...read<S["CastOut"]>(beingMade, "/cast"), state: "ready", asked: true, items: CAST_ITEMS.map((i) => (i.ref === "char:12" ? { ...i, approval: "changed", sig: "s2" } : i.ref === "slot:4" ? { ...i, readiness: "ready", preview_file_id: 404 } : i)) } });

const MUSIC: S["MusicOut"] = { name: "Low strings", file_id: 80, quieter_db: 8, gaps: "down", loop: false, removed: false, director: true };
const WATCH: S["WatchOut"] = { state: "done", found: "The cart kid says “I got it” once more than the script.", did: null, action: "flagged", note: "Say the line once, as written.", faults: [], waiting: false };
/** Delivered, with a second take on clip 4 (the one in the cut is flagged), sound effects on clip 3, music, and two
 *  edits waiting for the next cut. */
export const edited = over(delivered, {
  "/cut": { ...read<S["CutOut"]>(delivered, "/cut"), changes: 2, can_undo: true, timeline: { ...read<S["CutOut"]>(delivered, "/cut").timeline, music: MUSIC } },
  "/clips": read<S["ProjectClipOut"][]>(delivered, "/clips").map((c) => (c.clip_id === "c4" ? { ...c, takes: [{ ...c.takes[0], watch: WATCH }, { id: 124, number: 2, file_id: 224, created_at: "2026-11-13T09:30:00", verdict: "", mutes: [] }] } : c.clip_id === "c3" ? { ...c, sound: { ...c.sound!, state: "ready" } } : c)),
});

const VOICE = ask(10, { kind: "voice", topic: "The presenter’s voice", subject: "the presenter", question: "Which voice is the presenter?", why: "The whole video is timed to this voice.", can: ["voice", "again", "describe", "clone"], clone: { credits: 3, usd: 0.3 }, clone_to: "Saved to Palace Guard’s voices", created_at: "2026-11-13T09:22:00", audition: [{ id: "v1", name: "Warm", note: "Low and even", state: "done", sample_file_id: 601 }, { id: "v2", name: "Bright", note: "A little breathless", state: "done", sample_file_id: 602 }] });
const asked = (cards: S["AskOut"][]) => over(question, { "/asks": cards, "/director": runOf(question, { waiting: cards.map((c) => ({ id: c.id, topic: c.topic, question: c.question })), thread: cards.map((c) => said("ask", "09:21", { id: `a${c.id}`, ask_id: c.id })) as S["ThreadItem"][] }) });
/** A presenter with no voice yet: two voices that read the script, to hear and pick. */
export const voiceQuestion = asked([VOICE]);
/** The three looks it drew for the woman with the stroller. */
export const optionsQuestion = asked([{ ...QUESTION, state: "ready", can: ["option", "generate", "upload", "reply"], generate: { credits: 1, usd: 0.1 }, options_spent: { credits: 0.9, usd: 0.09 }, options: [701, 702, 703].map((file_id, index) => ({ index, state: "done", file_id })) }]);
/** Before any are drawn: the saved people, and the ways to make someone new, with the price of drawing. */
export const castQuestion = asked([{ ...QUESTION, generate: { credits: 1, usd: 0.1 } }]);
/** Two questions at once. */
export const twoQuestions = asked([QUESTION, VOICE]);

/** Archived after delivery; and the same video as the earlier, step-by-step director would have made it. */
export const archived = over(delivered, { "": { ...read<object>(delivered, ""), archived_at: "2026-11-13T10:00:00" }, "/idea": headOf(delivered, status("archived", "Archived")) });
export const earlier = over(delivered, { "": { ...read<object>(delivered, ""), engine: null } });

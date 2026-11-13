import type { components } from "../api/schema";
import { owner } from "./people";

/** One brand's Library as the server answers it, for the new look's page (studio/Library.tsx): `full` (a product with
 *  its photos, notes and clips, three saved people in the three states a sheet can be in, a saved place, footage in
 *  nested folders, a cloned voice, a look's voice and the app's) and `empty` (a brand with nothing saved). Each is a
 *  whole fake server: pass it to `fakeServer`. The shapes are the schema's own. */
type S = components["schemas"];
export type Routes = Record<string, [number, unknown]>;

/** "How it works" as he wrote it: a leading space, a tab, a blank line, two spaces and a trailing newline, all of
 *  which must come back untouched. */
export const HOW = " One hand holds the body.\tThe other hooks the ring and yanks it straight out, fast.\n\nThe moment the ring is out: a very loud whistle  and a hard white strobe.\n";

const item = (o: Partial<S["ItemOut"]> & Pick<S["ItemOut"], "id" | "name" | "kind">): S["ItemOut"] => ({ notes: "", brand_ids: [1], image_file_ids: [], outfits: [], presenter: false, version: 1, created_at: "2026-11-10T10:00:00Z", created_by_id: 1, pictures: [], sheet_file_id: null, sheet_status: "none", sheet_credits: 2, sheet_usual_credits: 2, change_credits: 1, usd: { sheet: 0.17, change: 0.08 }, advice: [], look_sheets: {}, used_in: [], used_in_count: 0, ...o });
export const alarm = item({ id: 54, kind: "prop", name: "Protector alarm", notes: HOW, product_type: "physical", short_description: "A white personal alarm with a ring at the top.", main_claim: "Loud enough to stop a stranger", version: 4, sheet_credits: 0, change_credits: 0, usd: null, pictures: [{ screen_id: 40, file_id: 41, name: "Protector alarm", variant: "" }, { screen_id: 42, file_id: 43, name: "Protector alarm (2)", variant: "In the hand" }] });
export const paige = item({ id: 179, kind: "character", name: "Paige", notes: "18, tall, volleyball sweatshirt", sheet_file_id: 301, sheet_status: "approved", voice_id: 7, version: 3, used_in_count: 1, used_in: [{ project_id: 366, name: "Three men at Target", status: "done", still_file_id: 90, at: "2026-11-12T10:00:00Z" }] });
export const dana = item({ id: 180, kind: "character", name: "Dana", notes: "Her mother, late forties", sheet_file_id: 302, sheet_status: "needs_approval", look_fit: { seen: "a woman in her twenties", problem: "Dana is in her late forties" } });
export const officer = item({ id: 181, kind: "character", name: "The officer", notes: "Fifties, dark uniform" });
const lot = item({ id: 21, kind: "place", name: "Target parking lot", sheet_file_id: 310, sheet_status: "approved" });

const folder = (id: number, name: string, parent_id: number | null): S["FolderOut"] => ({ id, brand_id: 1, parent_id, name, created_by_id: 1, can_manage: true, items: { scripts: 0, videos: 0, clips: 0, footage: 0 } as S["Items"] });
const clip = (id: number, description: string, folder_id: number | null, path: string, product_id: number | null): S["FootageOut"] => ({ id, file_id: 700 + id, thumb_file_id: 800 + id, seconds: 5, description, product_id, describing: false, note: "", folder_id, folder: path, competitor: false });
export const FOLDERS = [folder(1, "Product shots", null), folder(2, "Close-ups", 1), folder(3, "Campus", null)];
export const CLIPS = [clip(10, "A hand hooks the ring and pulls it out.", 1, "Product shots", 54), clip(11, "The strobe in a dark lot.", 2, "Product shots/Close-ups", 54), clip(12, "The alarm on a set of keys.", null, "", 54), clip(13, "A path across a quad.", 3, "Campus", null)];

const voice = (o: Partial<S["VoiceOut"]> & Pick<S["VoiceOut"], "name">): S["VoiceOut"] => ({ id: null, kind: "stock", stock_key: null, provider: "elevenlabs", description: "", look: null, brand_id: null, sample_file_id: null, sample_url: null, preview_file_id: null, cloned_at: null, last_used_at: null, expires_at: null, state: "ready", error: "", used_by: [], ...o });
const stock = (name: string, description: string) => voice({ name, stock_key: name, description, sample_url: `http://localhost:8000/voices/samples/${name}.mp3` });
export const VOICES: S["VoicesOut"] = {
  voices: [
    voice({ id: 7, name: "Kim", kind: "cloned", provider: "minimax", description: "Warm, fifties", brand_id: 1, sample_file_id: 60, used_by: [179] }),
    voice({ id: 8, name: "Dr. Pickle", kind: "cloned", provider: "minimax", description: "Deep, fixed", look: "dr-pickle", state: "may_expire", error: "Unused for 7 days: MiniMax may delete it soon." }),
    stock("Roger", "Relaxed man"),
    stock("Sarah", "Warm narrator"),
    stock("Hope", "Natural woman"),
    stock("George", "Older man, dry"),
  ],
  clone_credits: 29.18,
  clone_usd: 3,
};

const branch = { id: null, parent_id: null, name: "Unsorted", count: 0, can_manage: false, ideas: [], more: 0, folders: [] };
const shell: Routes = {
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Palace Guard", colours: ["#ef8a3c"] }]],
  "GET /workspace": [200, { id: 1, name: "Night Shift Studio" }],
  "GET /brands/1/tree": [200, { folders: [], unsorted: branch }],
  "GET /brands/1/ideas": [200, { total: 0, counts: { all: 0, needs_you: 0, working: 0, delivered: 0 }, archived: 0, folders_inside: 0, makers: [], ideas: [] }],
  "GET /looks": [200, [{ id: "house", name: "House", blurb: "", on: true }, { id: "dr-pickle", name: "Dr. Pickle", blurb: "", on: true }]],
  "GET /jobs": [200, []],
  "GET /library/character/price": [200, { credits: 2, usd: 0.17 }],
  "GET /brands/1/footage/price": [200, { credits: 1, usd: 0.02 }],
};

export const full: Routes = {
  ...shell,
  "GET /library/prop": [200, [alarm]],
  "GET /library/character": [200, [dana, paige, officer]],
  "GET /library/place": [200, [lot]],
  "GET /library/character/179": [200, paige],
  "GET /library/character/180": [200, dana],
  "GET /library/character/181": [200, officer],
  "GET /brands/1/footage": [200, CLIPS],
  "GET /brands/1/folders": [200, FOLDERS],
  "GET /brands/1/voices": [200, VOICES],
};

export const empty: Routes = {
  ...shell,
  "GET /library/prop": [200, []],
  "GET /library/character": [200, []],
  "GET /library/place": [200, []],
  "GET /brands/1/footage": [200, []],
  "GET /brands/1/folders": [200, []],
  "GET /brands/1/voices": [200, { ...VOICES, voices: VOICES.voices.filter((v) => v.kind === "stock") }],
};

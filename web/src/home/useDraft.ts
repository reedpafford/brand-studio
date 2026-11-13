import { useState } from "react";
import { useMe } from "../auth/useMe";
import { useFolders } from "../folders/Projects";
import type { Shape } from "../freestyle/useFreestyle";
import { useItems, type Item } from "../library/kinds";
import { useAttachments } from "../newvideo/Attach";
import type { Look } from "../newvideo/Cards";
import type { Mode, Send } from "../newvideo/useNewVideo";
import { notMadeAs, styleOf, useLooks } from "../scripts/Looks";
import { scriptSize } from "../scripts/ScriptFrame";
import { useFormats } from "../scripts/useFormats";
import { readsAsScript } from "./Words";

const MODE = "bs.newvideo.mode";
/** Ask before making, or (the owner only) make without asking; the owner's choice is remembered on this computer. */
export function useMode(owner: boolean): [Mode, (m: Mode) => void] {
  const [mode, setMode] = useState<Mode>(() => (localStorage.getItem(MODE) === "auto" ? "auto" : "ask"));
  return [owner ? mode : "ask", (m) => (localStorage.setItem(MODE, m), setMode(m))];
}

/** A brand's saved characters or products: the ones made in Cast & places, never a video's own. */
export function useSaved(kind: "character" | "prop", brandId: number) {
  const q = useItems(kind, brandId);
  return { ...q, data: q.data?.filter((i: Item) => !i.owner_project_id && !i.owner_script_id) };
}

type Picked = { type?: string; look?: string; broll_look?: string | null; shape?: Shape; folder?: number | null; cast?: number[]; products?: number[] };

/** What Home is about to send: the words, whether they are a script or an idea, the picked format, style, cast, products,
 *  shape, folder and mode, and the attached files. `fixed`: a saved script's own format and style. `opened`: the folder
 *  the person came from (?folder=). */
export function useDraft(brandId: number, opened: number | null, fixed: { type: string; look: string } | null) {
  const owner = useMe().data?.role === "owner";
  const formats = useFormats().data ?? [];
  const lookQuery = useLooks();
  const looks = (lookQuery.data ?? []) as Look[];
  const folders = useFolders(brandId).data ?? [];
  const [picked, setPicked] = useState<Picked>({});
  const pick = (p: Picked) => setPicked((was) => ({ ...was, ...p }));
  const [text, setText] = useState("");
  const [flipped, setIdea] = useState<boolean | null>(null); // the person's own flip wins over the guess
  const [mode, setMode] = useMode(owner);
  const files = useAttachments();
  const firstOn = <T extends { on: boolean; off?: string | null }>(xs: T[]) => xs.find((x) => x.on && !x.off);
  const format = formats.find((f) => f.id === (fixed?.type ?? picked.type)) ?? firstOn(formats);
  // A style made only in some formats (Movie: Dialogue only) isn't offered for another (QA on #1440).
  const only = (l: Look) => notMadeAs(l, format?.id, formats);
  // A script on one of a style's lanes ("paper-flat") shows as its style; brands keep no default style (S-gaps-05 L1).
  const look = looks.find((l) => (fixed ? l.id === styleOf(looks, fixed.look) : l.id === picked.look && !only(l))) ?? firstOn(looks.filter((l) => !only(l)));
  // A picked style the new format can't use is said, never swapped silently: "Movie is made only as Dialogue: … The style is House for now."
  const unused = fixed ? undefined : looks.find((l) => l.id === picked.look && only(l));
  const folder = picked.folder !== undefined ? picked.folder : folders.some((f) => f.id === opened) ? opened : null;
  const cast = picked.cast ?? []; // nobody until picked: brands keep no default cast
  const products = picked.products ?? [];
  const broll = format?.host ? (picked.broll_look ?? null) : null;
  const size = scriptSize(text); // never cut: past the most it says so, and nothing is priced or sent
  const idea = flipped ?? !readsAsScript(text);
  const send: Send = { brand_id: brandId, folder_id: folder, text: text.trim(), cast_ids: cast, product_ids: products, attachments: files.ids, idea, mode, type: format?.id ?? "dialogue", look: look?.id ?? "", shape: picked.shape ?? "9:16", broll_look: broll };
  // A style picked on Home's gallery. One not made in the picked format takes the first format it is made in, and `moved`
  // says so ("Movie is made only as Dialogue: … The format is Dialogue now.") until the style or format changes again.
  const [note, setNote] = useState<{ look?: string; type?: string; text: string } | null>(null);
  const pickStyle = (l: Look) => {
    const why = only(l);
    const to = why ? formats.find((f) => l.formats?.includes(f.id) && f.on && !f.off) : undefined;
    if (!why || to) pick({ look: l.id, broll_look: null, ...(to && { type: to.id }) });
    setNote(why ? { look: to ? l.id : look?.id, type: (to ?? format)?.id, text: to ? `${why} The format is ${to.name} now.` : why } : null);
  };
  const moved = note && note.look === look?.id && note.type === format?.id ? note.text : "";
  const toggle = (key: "cast" | "products", id: number) => {
    const was = key === "cast" ? cast : products;
    pick({ [key]: was.includes(id) ? was.filter((x) => x !== id) : [...was, id] });
  };
  return { owner, formats, looks, looksLoading: lookQuery.isPending, folders, format, look, only, unused, folder, cast, products, broll, text, setText, size, idea, setIdea, mode, setMode, files, pick, pickStyle, moved, toggle, send, fixed };
}
export type Draft = ReturnType<typeof useDraft>;

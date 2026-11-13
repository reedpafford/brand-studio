import type { Said } from "../freestyle/Thread";
import type { Freestyle } from "../freestyle/useFreestyle";
import { serverTime } from "../time";
import { treatmentOf } from "./Treatment";

/** A video's conversation, oldest first, as its page shows it. A freestyle's thread is its first words, its held sends
 *  and the director's moves in its words; each move keeps the run card or the delivery note it is (v6 piece C and D),
 *  from the video's own thread (`said`). The live card (the run `live`) sits after its run's other moves (the
 *  treatment, a held step), as the newest thing it says (S3-03). */
export function threadOf(fs: Freestyle | null, said: Said[], live: string | undefined): Said[] {
  const known = (t: Said) => said.find((x) => x.kind === "message" && x.who === t.who && x.text === t.text);
  const byId = new Map(said.map((x) => [x.id, x]));
  const items: Said[] = (fs
    ? [...fs.thread.map((t) => (t.kind === "message" ? { ...t, answered: known(t)?.answered } : { ...t, run: byId.get(t.id)?.run ?? null, note: byId.get(t.id)?.note ?? null })), ...said.filter((x) => x.kind === "message" && !fs.thread.some((t) => t.kind === "message" && t.who === x.who && t.text === x.text)).map((x) => ({ ...x, id: `note-${x.id}` })), ...said.filter((x) => x.kind === "ask")].sort((a, b) => serverTime(a.at).getTime() - serverTime(b.at).getTime())
    : [...said]);
  const at = items.findIndex((t) => t.run && t.run === live);
  if (at >= 0) {
    const [card] = items.splice(at, 1);
    const next = items.findIndex((t, i) => i >= at && (t.kind === "message" || t.note || t.run));
    const to = next < 0 ? items.length : next;
    // Moved below later cards, it never keeps the run's start time above them (MAIN's Claymation run: 01:07 under 01:17).
    const before = items[to - 1];
    const late = before && serverTime(before.at).getTime() > serverTime(card.at).getTime();
    items.splice(to, 0, late ? { ...card, at: before.at } : card);
  }
  return items;
}

/** A treatment a note replaced folds to its line, so the current one leads (H20): the one that leads. */
export const leadingTreatment = (items: Said[]) => [...items].reverse().find((t) => treatmentOf(t))?.id;

/** The newest note opens in full; once a later run starts (a revision), it folds to its line too (S3-12). */
export function openNote(items: Said[]) {
  const last = items.map((t) => !!t.note).lastIndexOf(true);
  return last >= 0 && !items.slice(last + 1).some((t) => t.run) ? items[last].id : undefined;
}

import { useMe } from "../auth/useMe";
import { Dot, type Tone } from "../components";
import type { Row } from "./data";

const WORDS: Record<Row["state"], [Tone, string, boolean?]> = {
  done: ["success", "In the cut"],
  redone: ["success", "Redone"],
  text: ["success", "Redone"],
  flagged: ["warning", "Flagged"],
  waiting: ["warning", "Waiting for the owner", true],
  failed: ["danger", "Failed"],
  making: ["accent", "Making"],
  todo: ["neutral", "Not made yet", true],
  too_long: ["danger", "Too long for its model"], // S3-11: the stuck card says why and offers Split it
};

/** What a waiting clip says to the owner, who is the one to OK it (MAIN's run, video 233: never "Waiting for the owner"). */
const yours = (r: Row) => (/\bcast\b/i.test(r.note) ? "Waiting for your cast OK" : "Waiting for your OK");

/** A row's state in words with a dot (S6-05). The phone says Done for a clip in the cut (P-10). `wrap`: a narrow card's,
 *  whose words go onto a second line rather than past its edge. */
export function RowStatus({ r, phone, wrap }: { r: Row; phone?: boolean; wrap?: boolean }) {
  const owner = useMe().data?.role === "owner";
  const [tone, plain, hollow] = WORDS[r.state] ?? WORDS.todo; // a state this screen doesn't know yet never breaks it
  const word = r.state === "waiting" && owner ? yours(r) : plain;
  const colour = tone === "success" ? "text-success" : tone === "warning" ? "text-warning" : tone === "danger" ? "text-danger" : tone === "accent" ? "text-accent-text" : "text-muted";
  const said = r.state === "making" && r.minutes_left ? `Making · about ${r.minutes_left} min` : phone && r.state === "done" ? "Done" : word;
  return (
    <span className={`${wrap ? "min-w-0 leading-4" : "shrink-0"} text-xs font-medium ${colour}`}>
      <Dot tone={tone} hollow={hollow}>
        {wrap ? <span className="min-w-0 whitespace-normal">{said}</span> : said}
      </Dot>
    </span>
  );
}


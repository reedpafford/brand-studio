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

/** A row's state in words with a dot (S6-05). The phone says Done for a clip in the cut (P-10). */
export function RowStatus({ r, phone }: { r: Row; phone?: boolean }) {
  const [tone, word, hollow] = WORDS[r.state] ?? WORDS.todo; // a state this screen doesn't know yet never breaks it
  const colour = tone === "success" ? "text-success" : tone === "warning" ? "text-warning" : tone === "danger" ? "text-danger" : tone === "accent" ? "text-accent-text" : "text-muted";
  const said = r.state === "making" && r.minutes_left ? `Making · about ${r.minutes_left} min` : phone && r.state === "done" ? "Done" : word;
  return (
    <span className={`shrink-0 text-xs font-medium ${colour}`}>
      <Dot tone={tone} hollow={hollow}>
        {said}
      </Dot>
    </span>
  );
}


import { useState, type ReactNode, type Ref } from "react";
import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { fileUrl } from "../api/upload";
import type { components } from "../api/schema";
import type { Tone } from "../components";
import { plain } from "../videos/director";
import { serverTime } from "../time";
import { STATUS, type Freestyle } from "./useFreestyle";
import { TreatmentCard, treatmentOf } from "../videos/Treatment";

const DOT: Record<Tone, string> = { warning: "bg-warning", accent: "bg-accent", success: "bg-success", danger: "bg-danger", neutral: "bg-faint", media: "bg-faint" };

/** A status as a dot and its words ("Waiting for approval"), with an optional tail ("· 29 Oct"). */
export function Status({ status, tail, words }: { status: Freestyle["status"]; tail?: string; words?: string }) {
  const s = STATUS[status];
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm text-muted">
      <span aria-hidden className={`size-2 shrink-0 rounded-full ${DOT[s.tone]}`} />
      {words ?? s.words}
      {tail && ` · ${tail}`}
    </span>
  );
}

export const Tag = ({ children }: { children: string }) => <span className="rounded-sm border border-border px-1.5 text-sm leading-5 text-muted">{children}</span>;

const clock = (iso: string) => {
  const d = serverTime(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
};

const OK = "Waiting for the owner's OK"; // what a held send says to an editor (the server's WAIT_OK)
export type Said = components["schemas"]["ThreadItem"]; // a FreestyleItem, with `answered` on a note

// A script line: a speaker's ("DR. PICKLE: …") or a scene heading.
const SCRIPTY = /^([A-Z0-9][A-Z0-9 .'’-]{0,40}:|SCENE\b|INT\.|EXT\.)/;

/** A pasted script in the first message (S3-01): the words before it as they are, then its first two lines in a box with
 *  how many more. */
function Excerpt({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const all = text.split("\n").filter((l) => l.trim());
  const at = Math.max(0, all.findIndex((l) => SCRIPTY.test(l.trim())));
  const lines = all.slice(at);
  return (
    <>
      {at > 0 && <p className="whitespace-pre-line break-words">{all.slice(0, at).join("\n")}</p>}
      <div className="mt-1.5 rounded-md border border-border bg-surface px-2.5 py-2 font-script text-[13px] leading-[1.55]">
      {(open ? lines : lines.slice(0, 2)).map((l, i) => (
        <p key={i} className="break-words">{l}</p>
      ))}
      {lines.length > 2 && (
        <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="text-muted hover:text-text max-lg:min-h-control">
          {open ? "Show less" : `+ ${lines.length - 2} more line${lines.length === 3 ? "" : "s"}`}
        </button>
      )}
      </div>
    </>
  );
}

/** One line of a conversation with the director (S3): an avatar, who and when, then the words; a person's in a bubble. A
 *  person's note says whether a move has answered it; a move gives its reason under it in muted words, one under way
 *  shows the typing dots, and a held move links the owner to Needs you (an editor reads that it waits) unless `children`
 *  (a price card) under it say so. `first`: what the first message carries in place of its words (a saved script);
 *  `excerpt`: it's the first message, so a pasted script shows as its first lines. */
export function Item({ t, words, why, owner, children, first, excerpt, ref }: { t: Said; words: ReactNode; why?: string; owner?: boolean; children?: ReactNode; first?: ReactNode; excerpt?: boolean; ref?: Ref<HTMLLIElement> }) {
  const director = t.kind === "move" || t.kind === "ask"; // a card is the director asking
  const story = director ? treatmentOf(t) : null; // the treatment: a card in place of its plain lines (#1192)
  const going = director && (t.status === "running" || t.status === "queued");
  // A long paste (a script) shows its first lines; a short ask reads as it is.
  // The first message, when it carries a script: its first lines in a box, the rest a press away (S3-01).
  const lines = typeof words === "string" ? words.split("\n").filter((l) => l.trim()) : [];
  const script = !director && !!excerpt && lines.length > 2 && lines.some((l) => SCRIPTY.test(l.trim()));
  return (
    <li ref={ref} className="flex min-w-0 gap-2.5">
      <span aria-hidden className={`grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold ${director ? "bg-ink text-white" : "bg-accent-soft text-accent-text"}`}>
        {director ? <Sparkles size={12} strokeWidth={1.75} /> : t.who.slice(0, 1).toUpperCase()}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <p className="flex items-baseline gap-1.5 text-sm font-semibold">
          {t.who}
          <span className="text-xs font-normal text-muted tabular-nums">
            {clock(t.at)}
            {t.status === "refused" && " · couldn't do it"}
            {t.answered === true && " · Answered"}
            {t.answered === false && " · Open"}
          </span>
        </p>
        {director ? (
          <div className="min-w-0 space-y-1 empty:hidden">
            {story ? (
              <TreatmentCard t={story} changed={t.text.startsWith("Changed the treatment")} />
            ) : going && words != null ? (
              <p className="flex items-center gap-2 text-sm text-muted">
                <span aria-hidden className="inline-flex h-5 items-center gap-1">
                  <i className="size-1.5 rounded-full bg-faint" />
                  <i className="size-1.5 rounded-full bg-faint opacity-70" />
                  <i className="size-1.5 rounded-full bg-faint opacity-40" />
                </span>
                <span className="break-words">{words}</span>
                <span className="sr-only"> (working)</span>
              </p>
            ) : (
              words != null && <div className="whitespace-pre-line break-words leading-[21px]">{words}</div>
            )}
            {why && <p className="break-words text-muted">{why}</p>}
            {t.status === "held" && !children &&
              (owner ? (
                <Link to="/approvals" className="inline-block text-accent-text underline-offset-2 hover:underline">
                  See it in Needs you
                </Link>
              ) : (
                !t.text.startsWith(OK) && <p className="text-muted">{OK}.</p> // an editor: always the owner, never a name
              ))}
          </div>
        ) : (
          <>
            {(words != null || first) && (
              <div className="min-w-0 rounded-[10px] bg-surface-2 px-3 py-2 leading-[21px]">
                {script ? <Excerpt text={words as string} /> : words != null && <p className="whitespace-pre-line break-words">{words}</p>}
                {first}
              </div>
            )}
            <Attached ids={(t as { files?: number[] | null }).files ?? []} />
          </>
        )}
        {children}
      </div>
    </li>
  );
}

/** An older freestyle's thread (/freestyle/:id), oldest first: the first message carries the settings as tags and the
 *  words in the script font. A director-run freestyle's moves are made plain the way a video's are. */
export function Thread({ fs, tags }: { fs: Freestyle; tags: string[] }) {
  const opening = fs.thread.find((t) => t.kind === "message")?.id;
  const say = (text: string) => (fs.type === "one_clip" ? text : plain(text, []));
  return (
    <ol aria-label="Thread" className="flex flex-col gap-6">
      {fs.thread.map((t) =>
        t.kind === "message" ? (
          <Item key={t.id} t={t} words={t.id === opening ? null : t.text}>
            {t.id === opening && (
              <>
                <div className="flex flex-wrap gap-1.5" aria-label="Settings">
                  {tags.map((x) => (
                    <Tag key={x}>{x}</Tag>
                  ))}
                </div>
                <p className="whitespace-pre-line break-words font-script text-sm leading-[1.6] text-muted">{t.text}</p>
              </>
            )}
          </Item>
        ) : (
          <Item key={t.id} t={t} words={say(t.text) || "Deciding what to do next."} why={say(t.why ?? "")} />
        ),
      )}
    </ol>
  );
}

/** The pictures or clips sent with a message (New video's, or with a note in the chat), for this video only (rule 12). */
function Attached({ ids }: { ids: number[] }) {
  if (!ids.length) return null;
  return (
    <ul aria-label="Attached for this video" className="flex flex-wrap gap-2">
      {ids.map((id) => (
        <li key={id} className="h-16 w-12 overflow-hidden rounded-md bg-surface-3">
          <a href={fileUrl(id)} target="_blank" rel="noreferrer" aria-label="Open the attachment">
            <Thumb src={fileUrl(id)} />
          </a>
        </li>
      ))}
    </ul>
  );
}

/** A picture, or a clip's first frame when it isn't one. */
function Thumb({ src }: { src: string }) {
  const [clip, setClip] = useState(false);
  return clip ? <video src={src} muted preload="metadata" className="size-full object-cover" /> : <img src={src} alt="" onError={() => setClip(true)} className="size-full object-cover" />;
}

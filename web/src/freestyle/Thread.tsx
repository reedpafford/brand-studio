import type { ReactNode, Ref } from "react";
import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import type { components } from "../api/schema";
import type { Tone } from "../components";
import { plain } from "../projects/DirectorPanel";
import { serverTime } from "../time";
import { STATUS, type Freestyle } from "./useFreestyle";

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

export type Said = components["schemas"]["ThreadItem"]; // a FreestyleItem, with `answered` on a note

/** One line of a conversation with the director (B_VideoRunning): an avatar, who and when, then the words. A person's
 *  note says whether a move has answered it; a move gives its reason under it in muted words, and a held move links the
 *  owner to Needs you (an editor reads that it waits) unless `children` (the cut, a price card) under it say so. */
export function Item({ t, words, why, owner, children, ref }: { t: Said; words: ReactNode; why?: string; owner?: boolean; children?: ReactNode; ref?: Ref<HTMLLIElement> }) {
  const director = t.kind === "move";
  return (
    <li ref={ref} className="flex min-w-0 gap-3">
      <span aria-hidden className={`grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold ${director ? "bg-accent-soft text-accent-text" : "bg-surface-3 text-text"}`}>
        {director ? <Sparkles size={12} strokeWidth={1.75} /> : t.who.slice(0, 1).toUpperCase()}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p className="text-sm">
          <span className="font-medium">{t.who}</span>{" "}
          <span className="text-muted tabular-nums">
            {clock(t.at)}
            {t.status === "running" && " · working"}
            {t.status === "refused" && " · couldn't do it"}
            {t.answered === true && " · Answered"}
            {t.answered === false && " · Open"}
          </span>
        </p>
        <div className="min-w-0 space-y-1 empty:hidden">
          {words != null && <div className="whitespace-pre-line break-words">{words}</div>}
          {why && <p className="break-words text-muted">{why}</p>}
          {t.status === "held" && !children &&
            (owner ? (
              <Link to="/approvals" className="inline-block text-accent-text underline-offset-2 hover:underline">
                See it in Needs you
              </Link>
            ) : (
              <p className="text-muted">Waiting for approval.</p>
            ))}
        </div>
        {children}
      </div>
    </li>
  );
}

/** The freestyle's thread, oldest first, newest at the bottom. The first message carries the settings as tags and the
 *  words in the script font (`first` replaces those words: a script it came from). A director-run freestyle's moves are
 *  made plain the way a video's are: no tool names, codes or JSON on screen. `extra` adds what sits under an item. */
export function Thread({ fs, items = fs.thread, tags, owner, first, extra }: { fs: Freestyle; items?: Said[]; tags: string[]; owner?: boolean; first?: ReactNode; extra?: (t: Said) => ReactNode }) {
  const opening = items.find((t) => t.kind === "message")?.id;
  const say = (text: string) => (fs.type === "one_clip" ? text : plain(text, []));
  return (
    <ol aria-label="Thread" className="flex flex-col gap-6">
      {items.map((t) =>
        t.kind === "message" ? (
          <Item key={t.id} t={t} words={t.id === opening ? null : t.text}>
            {t.id === opening && (
              <>
                {first}
                <div className="flex flex-wrap gap-1.5" aria-label="Settings">
                  {tags.map((x) => (
                    <Tag key={x}>{x}</Tag>
                  ))}
                </div>
                {!first && <p className="whitespace-pre-line break-words font-script text-sm leading-[1.6] text-muted">{t.text}</p>}
              </>
            )}
            {extra?.(t)}
          </Item>
        ) : (
          <Item key={t.id} t={t} owner={owner} words={say(t.text) || "Deciding what to do next."} why={say(t.why ?? "")}>
            {extra?.(t)}
          </Item>
        ),
      )}
    </ol>
  );
}

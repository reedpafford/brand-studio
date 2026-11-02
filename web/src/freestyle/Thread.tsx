import { Sparkles } from "lucide-react";
import type { Tone } from "../components";
import { plain } from "../projects/DirectorPanel";
import { serverTime } from "../time";
import { STATUS, type Freestyle } from "./useFreestyle";

const DOT: Record<Tone, string> = { warning: "bg-warning", accent: "bg-accent", success: "bg-success", danger: "bg-danger", neutral: "bg-faint", media: "bg-faint" };

/** A status as a dot and its words ("Waiting for approval"), with an optional tail ("· 29 Oct"). */
export function Status({ status, tail }: { status: Freestyle["status"]; tail?: string }) {
  const s = STATUS[status];
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm text-muted">
      <span aria-hidden className={`size-2 shrink-0 rounded-full ${DOT[s.tone]}`} />
      {s.words}
      {tail && ` · ${tail}`}
    </span>
  );
}

export const Tag = ({ children }: { children: string }) => <span className="rounded-sm border border-border px-1.5 text-xs leading-5 text-muted">{children}</span>;

const clock = (iso: string) => serverTime(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

/** The thread, oldest first, newest at the bottom: people's messages on the right, the director's moves on the left with
 *  why under them. The first message carries the freestyle's settings as tags. A director-run freestyle's (Dialogue's)
 *  moves are made plain the way a video's director thread is: no tool names, codes or JSON on screen. */
export function Thread({ fs, tags }: { fs: Freestyle; tags: string[] }) {
  const first = fs.thread.find((t) => t.kind === "message")?.id;
  const say = (text: string) => (fs.type === "one_clip" ? text : plain(text, []));
  return (
    <ol aria-label="Thread" className="flex flex-col gap-5">
      {fs.thread.map((t) =>
        t.kind === "message" ? (
          <li key={t.id} className="ml-auto flex max-w-[85%] min-w-0 flex-col items-end gap-1.5">
            <p className="text-sm">
              <span className="font-medium">{t.who}</span> <span className="text-muted">{clock(t.at)}</span>
            </p>
            {t.id === first && (
              <div className="flex flex-wrap justify-end gap-1.5" aria-label="Settings">
                {tags.map((x) => (
                  <Tag key={x}>{x}</Tag>
                ))}
              </div>
            )}
            <p className="whitespace-pre-line break-words rounded-lg bg-surface-2 px-3 py-2 font-script text-sm">{t.text}</p>
          </li>
        ) : (
          <li key={t.id} className="flex max-w-[85%] min-w-0 gap-3">
            <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-text">
              <Sparkles size={12} strokeWidth={1.75} />
            </span>
            <div className="min-w-0 space-y-0.5 text-sm">
              <p>
                <span className="font-medium">{t.who}</span> <span className="text-muted">{clock(t.at)}</span>
              </p>
              <p className="break-words">{say(t.text) || "Deciding what to do next."}</p>
              {say(t.why) && <p className="break-words text-muted">{say(t.why)}</p>}
            </div>
          </li>
        ),
      )}
    </ol>
  );
}

import { Fragment, useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

/** The working (newest) script, or null when there is none yet. */
export function useLatestScript(projectId: number) {
  return useQuery({
    queryKey: ["script", projectId],
    enabled: projectId > 0,
    queryFn: async () => {
      const { data, response } = await api.GET("/projects/{project_id}/script", { params: { path: { project_id: projectId } } });
      if (response.status === 404) return null;
      if (!data) throw new Error("load");
      return data;
    },
  });
}

/** Line-numbered, in the script font, wrapping at about 64 characters. The words are never altered.
 *  `around` can put other lines (Enhance direction notes) before or after a script line. */
const DIRECTION = /^\s*\[(Camera|Movement|Reaction|Brand screen)\]\s*/;

/** A line with each of `words` marked where it's said (S3-14: the words someone asked to change). */
function markWords(line: string, words: string[]): ReactNode {
  const said = words.filter(Boolean).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/['’‘]/g, "['’‘]").replace(/\s+/g, "\\s+"));
  if (!said.length) return line;
  return line.split(new RegExp(`(${said.join("|")})`, "i")).map((part, i) => (i % 2 ? <mark key={i} className="bg-mark px-0.5 text-inherit">{part}</mark> : part));
}

export function ScriptText({ text, around, highlight = [], rewritten = [], marks = [], onLineClick }: { text: string; around?: (line: number, where: "before" | "after") => ReactNode; highlight?: number[]; /** Lines (1-based) rewritten for the brand swap: marked like Directions. */ rewritten?: number[]; /** Words to mark where they're said. */ marks?: string[]; onLineClick?: (line: number) => void }) {
  // Bring the first highlighted line into view when the highlight changes.
  const marked = highlight.join(",");
  useEffect(() => {
    document.querySelector("[data-hl=true]")?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [marked]);
  return (
    <div className="max-w-[72ch] break-words rounded-md border border-border bg-surface p-4 font-script leading-[1.6] [overflow-wrap:anywhere]">
      <ol aria-label="Script text">
        {text.split("\n").map((line, i) => {
          // Directions that Enhance added are tagged lines. They never look like dialogue: indented and muted, tag as the label.
          const tag = DIRECTION.exec(line);
          return (
            <Fragment key={i}>
              {around?.(i + 1, "before")}
              <li className={`grid grid-cols-[2.5rem_1fr] items-baseline gap-2 ${onLineClick ? "max-lg:grid-cols-[2.75rem_1fr]" : ""} ${highlight.includes(i + 1) ? "bg-accent-soft" : ""}`} data-direction={tag ? tag[1] : undefined} data-hl={highlight.includes(i + 1) || undefined}>
                {onLineClick ? (
                  <button type="button" className="text-right text-xs text-faint underline max-lg:min-h-control" aria-label={`Show line ${i + 1} in the breakdown`} onClick={() => onLineClick(i + 1)}>
                    {i + 1}
                  </button>
                ) : (
                  <span className="select-none text-right text-xs text-faint" aria-hidden>
                    {i + 1}
                  </span>
                )}
                {tag ? (
                  // The words, then the kind in a fixed column, as Directions lines up its suggestions (QA-3 on #1191).
                  <span className="ml-4 grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 text-muted sm:ml-0 sm:grid-cols-[minmax(0,1fr)_6.5rem_12rem]">
                    <span className="whitespace-pre-wrap [overflow-wrap:anywhere]">
                      {tag[1] === "Brand screen" ? "★ " : "▸ "}
                      {line.slice(tag[0].length)}
                    </span>
                    <span className="font-sans text-xs">{tag[1]}</span>
                  </span>
                ) : (
                  <span className={`whitespace-pre-wrap [overflow-wrap:anywhere] ${rewritten.includes(i + 1) ? "bg-mark underline decoration-mark-line decoration-2 underline-offset-2" : ""}`}>{line ? markWords(line, marks) : "\u00a0"}</span>
                )}
              </li>
              {around?.(i + 1, "after")}
            </Fragment>
          );
        })}
      </ol>
    </div>
  );
}

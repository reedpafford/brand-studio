import { useLayoutEffect, useRef, type FocusEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, FileInput, FileText, Mic, Music, Plus } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Button, Card, Menu, MenuItem, TextArea, buttonClass } from "../components";
import { errorText as errorClass } from "../ui";
import { songsQuery } from "./useSongs";

export const UNTITLED = "Untitled script";
type Kind = "story" | "song" | "narrated";
const KINDS: Record<Kind, string> = { story: "Dialogue", song: "Song", narrated: "Narrated" };

/** New script: the format first, Dialogue, Song or Narrated (flows S1). Nothing is saved yet: that waits for the first word (NewScriptPage). */
export function NewScriptButton({ brandId }: { brandId: number }) {
  const navigate = useNavigate();
  const choice = (kind: Kind, Icon: typeof FileText, about: string, close: () => void) => (
    <MenuItem
      onClick={() => {
        close();
        navigate(`/b/${brandId}/scripts/new?kind=${kind}`);
      }}
    >
      <Icon size={20} strokeWidth={1.75} aria-hidden />
      <span className="flex-1 py-2">
        <span className="block font-medium">{KINDS[kind]}</span>
        <span className="block text-sm text-muted">{about}</span>
      </span>
    </MenuItem>
  );
  return (
    <Menu
      title="New script"
      align="right"
      trigger={(p) => (
        <Button icon={Plus} {...p}>
          New script
        </Button>
      )}
    >
      {(close) => (
        <>
          {choice("story", FileText, "People speak on camera", close)}
          {choice("song", Music, "Your lyrics, sung word for word over a music video", close)}
          {choice("narrated", Mic, "One voice reads your script over B-roll, with music", close)}
        </>
      )}
    </Menu>
  );
}

/** The first box of each format, the same here and on the step, so the swap between them can't be seen. */
export const SCRIPT_BOX = { label: "Paste or write your script", rows: 14, maxLength: 50000, placeholder: "Paste or write the script here" };
export const LYRICS_BOX = { label: "Lyrics", rows: 12, placeholder: "[Verse]\nPaste or write the lyrics here" };

/** The words typed here go on as the step's unsaved draft (its tab memory), so its Save works as it always does. */
const memory = (kind: Kind, id: number) => (kind === "song" ? `song-words-${id}` : `script-words-${id}`);
const keeps = () => {
  try {
    sessionStorage.setItem("new-script", "1");
    sessionStorage.removeItem("new-script");
    return true;
  } catch {
    return false; // a private window: the words are saved with the script instead
  }
};

/** Arriving from NewScriptPage mid-word: the editor takes the cursor, at the end of what was typed. The new page is drawn while
 *  the old box still takes keys, so on arrival the editor reads its tab memory once more (`catchUp`) for the last of them. */
export function useTypingOn(catchUp: () => void) {
  const typing = !!(useLocation().state as { typing?: boolean } | null)?.typing;
  useLayoutEffect(() => {
    if (typing) catchUp();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return typing ? { autoFocus: true, onFocus: (e: FocusEvent<HTMLTextAreaElement>) => e.currentTarget.setSelectionRange(e.currentTarget.value.length, e.currentTarget.value.length) } : {};
}

/** A new script before it exists (flows S1 U): the format's first box. The first word typed saves it, with its format, and
 *  opens its page with the words still in the box; leaving before that leaves nothing behind. */
export function NewScriptPage() {
  const brandId = Number(useParams().brandId);
  const kind = useSearchParams()[0].get("kind") as Kind;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const latest = useRef(""); // the box keeps its own words; what's typed while the save is on its way goes along too
  const started = useRef(false); // set at once, before a re-render, so a fast double tap or two quick letters make one script
  const saved = useRef<number | null>(null); // the script, once made: from then on every key goes on to its editor's tab memory
  const hand = (id: number, words: string) => {
    try {
      if (words) sessionStorage.setItem(memory(kind, id), kind === "song" ? JSON.stringify({ text: words, style: "" }) : words);
    } catch {
      /* a private window: saved with it */
    }
  };
  const make = useMutation({
    mutationFn: async (typed: string) => {
      const text = keeps() ? "" : typed;
      // "narrated" is Next-Server's #858; the generated types carry it once that's on next.
      const { data, error } = await api.POST("/scripts", { body: { brand_id: brandId, title: UNTITLED, description: "", notes: "", reference_replace: "", text, kind: kind as "story" } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onError: () => {
      started.current = false;
    },
    onSuccess: async (made) => {
      // The script page opens with its editor already there (no loading screen for keys to fall into): the save returned the
      // script, and a voiced one's takes are loaded first. Typing meanwhile still lands in this box.
      queryClient.setQueryData(["script-lib", made.id], made);
      if (kind !== "story") await queryClient.ensureQueryData(songsQuery(made.id)).catch(() => undefined);
      void queryClient.invalidateQueries({ queryKey: ["scripts"] });
      const words = latest.current; // read last, just before the swap, so nothing typed while saving is lost
      saved.current = made.id;
      hand(made.id, words);
      navigate(`/b/${brandId}/scripts/${made.id}`, { replace: true, state: words ? { typing: true } : { about: true } });
    },
  });
  if (!(kind in KINDS)) return <Navigate to={`/b/${brandId}/scripts`} replace />;
  const start = (text: string) => {
    if (started.current) return;
    started.current = true;
    make.mutate(text);
  };
  const type = (text: string) => {
    latest.current = text;
    if (saved.current !== null) hand(saved.current, text);
    if (text.trim()) start(text);
  };
  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-8">
      <Link to={`/b/${brandId}/scripts`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline lg:min-h-control-dense">
        <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
        Scripts
      </Link>
      <h1 className="type-page">{UNTITLED}</h1>
      <p className="text-sm text-muted">{KINDS[kind]} · saved when you type the first word.</p>
      <Card className="max-w-[680px] space-y-3">
        <TextArea {...(kind === "song" ? LYRICS_BOX : SCRIPT_BOX)} autoFocus onChange={(e) => type(e.target.value)} />
        {make.isError && <p role="alert" className={errorClass}>{make.error.message} Type again to try again.</p>}
      </Card>
      <div className="space-y-1">
        <Button variant="secondary" disabled={make.isPending} onClick={() => start("")}>
          Start from what it's for
        </Button>
        <p className="text-sm text-muted">{kind === "song" ? "Saves it and opens Song, where Claude can suggest directions." : "Saves it and opens About, where Claude can write it for you."}</p>
      </div>
    </main>
  );
}

/** Import a reel starts from a link or a video, not words, so it keeps its own page. */
export function ImportReelLink({ brandId }: { brandId: number }) {
  return (
    <Link to={`/b/${brandId}/scripts/import`} className={buttonClass("secondary")}>
      <FileInput size={20} strokeWidth={1.75} aria-hidden />
      Import a reel
    </Link>
  );
}

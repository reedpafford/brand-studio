import { useLayoutEffect, useRef, useState, type FocusEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, FileText, Mic, Music, Plus } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Button, Menu, MenuItem, StepPicker, TextArea, buttonClass } from "../components";
import { useBrands } from "../shell/useBrands";
import { useLanguages } from "../languages/useLanguages";
import { PickLabel, ScriptBox, ScriptTop, SettingsRow, ShapeChip, pickClass } from "./ScriptFrame";
import { useMe } from "../auth/useMe";
import { useFolders } from "../folders/Projects";
import { stepStates, stepsFor } from "./flow";
import type { Script } from "./useScript";
import { LookPicker, lookName, useLooks } from "./Looks";
import { errorText as errorClass } from "../ui";
import { songsQuery } from "./useSongs";
import { useFormats, type Format } from "./useFormats";

export const UNTITLED = "Untitled script";
const ICON = { story: FileText, song: Music, narrated: Mic };

/** New script: the format first, one of the guides' formats that are on (flows S1). Nothing is saved yet: that waits for the first word (NewScriptPage). */
export function NewScriptButton({ brandId }: { brandId: number }) {
  const navigate = useNavigate();
  const formats = (useFormats().data ?? []).filter((f) => f.on);
  return (
    <Menu
      title="New script"
      align="right"
      trigger={(p) => (
        <Button icon={Plus} className="shrink-0 whitespace-nowrap" {...p}>
          New script
        </Button>
      )}
    >
      {(close) =>
        formats.map((f) => {
          const Icon = ICON[f.engine];
          return (
            <MenuItem
              key={f.id}
              onClick={() => {
                close();
                navigate(`/b/${brandId}/scripts/new?format=${f.id}`);
              }}
            >
              <Icon size={20} strokeWidth={1.75} aria-hidden />
              <span className="flex-1 py-2">
                <span className="block font-medium">{f.name}</span>
                <span className="block text-sm text-muted">{f.blurb}</span>
              </span>
            </MenuItem>
          );
        })
      }
    </Menu>
  );
}

/** The first box of each format, the same here and on the step, so the swap between them can't be seen. */
export const LYRICS_BOX = { label: "Lyrics", rows: 12, placeholder: "[Verse]\nPaste or write the lyrics here" };

/** The words typed here go on as the step's unsaved draft (its tab memory), so its Save works as it always does. */
const memory = (kind: Format["engine"], id: number) => (kind === "song" ? `song-words-${id}` : `script-words-${id}`);
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
  const formats = useFormats().data;
  const [params, setParams] = useSearchParams();
  const format = formats?.find((f) => f.id === params.get("format") && f.on);
  const kind = format?.engine ?? "story"; // the format's engine runs it
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
  const me = useMe().data;
  const looks = useLooks();
  const brand = useBrands().data?.find((b) => b.id === brandId);
  const languages = useLanguages();
  const folders = useFolders(brandId);
  const [picking, setPicking] = useState(false);
  // A Look or Project pick saves the script with it (flows S1 U: the first press saves it, never just opening the page).
  const make = useMutation({
    mutationFn: async (start: { text: string; look?: string; folder?: number; language?: string }) => {
      const text = keeps() ? "" : start.text;
      const { data, error } = await api.POST("/scripts", { body: { brand_id: brandId, title: UNTITLED, description: "", notes: "", reference_replace: "", text, kind, format: format?.id, ...(start.look ? { look: start.look } : {}), ...(start.language ? { language: start.language } : {}) } });
      if (!data) throw new Error(errorText(error));
      if (start.folder != null) await api.POST("/folders/file", { body: { kind: "script", id: data.id, folder_id: start.folder } });
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
      // A new script stays on its first step, ready for the words (the Overview is for scripts with some).
      navigate(`/b/${brandId}/scripts/${made.id}?step=${stepsFor(made)[0].id}`, { replace: true, state: words ? { typing: true } : undefined });
    },
  });
  if (!formats) return null;
  if (!format) return <Navigate to={`/b/${brandId}/scripts`} replace />;
  const start = (text: string, with_: { look?: string; folder?: number; language?: string } = {}) => {
    if (started.current) return;
    started.current = true;
    make.mutate({ text, ...with_ });
  };
  // The script page's own header, before the script exists: the format, Look and Project, and the steps (later ones locked).
  const look = brand?.default_look ?? looks.data?.[0]?.id ?? "house";
  // The same steps and reasons the script's own page shows for an empty script.
  const empty = { kind, published: false, versions: [{ slot: 0, text: "", status: "draft" }] } as unknown as Script;
  // Every step after the first is locked with its reason: none can be opened before the script exists (QA-3 on #1191).
  const steps = stepStates(stepsFor(empty)[0].id, empty)
    // Publish is "Publish to library", not a step in the bar, for stories and songs alike (v5; ScriptFlowPage's barSteps).
    .filter((x) => (kind !== "story" && kind !== "song") || x.id !== "publish")
    .map((x, n) => (n === 0 ? x : { ...x, state: "todo" as const, reason: kind === "song" ? "Write or pick the lyrics first" : "Write a few lines first" }));
  const type = (text: string) => {
    latest.current = text;
    if (saved.current !== null) hand(saved.current, text);
    if (text.trim()) start(text);
  };
  const lang = brand?.default_language ?? "en";
  const langName = (id: string) => languages.data?.find((l) => l.id === id)?.name ?? (id === "en" ? "English" : id);
  const picks = (languages.data ?? []).filter((l) => l.on || me?.role === "owner");
  return (
    <main>
      <ScriptTop
        crumbs={[
          <Link key="s" to={`/b/${brandId}/scripts`} className="inline-flex min-h-control min-w-11 items-center hover:text-text hover:underline lg:min-h-0 lg:min-w-0">
            Scripts
          </Link>,
          <span key="n" className="font-medium text-text">
            New script
          </span>,
        ]}
      >
        <Link to={`/b/${brandId}/scripts/import`} className={`${buttonClass("secondary")} whitespace-nowrap lg:min-h-control-dense lg:px-3 lg:text-sm`}>
          Import a reel instead
        </Link>
      </ScriptTop>
      {/* v5 C_NewScript: Type, Style, Project and Language; each pick saves the script with it (flows S1 U). */}
      <SettingsRow steps={<StepPicker flat steps={steps} onPick={() => {}} />}>
        <Menu title="Type" trigger={(t) => <Button variant="ghost" dense trailing={ChevronDown} className={pickClass} aria-label={`Type: ${format.name}`} {...t}><PickLabel label="Type">{format.name}</PickLabel></Button>}>
          {(close) =>
            formats.filter((f) => f.on).map((f) => (
              <MenuItem key={f.id} onClick={() => { close(); setParams({ format: f.id }, { replace: true }); }}>
                {f.name}{f.id === format.id ? " ✓" : ""}
              </MenuItem>
            ))
          }
        </Menu>
        {looks.data && (
          <Button variant="ghost" dense trailing={ChevronDown} className={pickClass} aria-label={`Style: ${lookName(looks.data, look)}`} aria-haspopup="dialog" disabled={make.isPending} onClick={() => setPicking(true)}>
            <PickLabel label="Style">{lookName(looks.data, look)}</PickLabel>
          </Button>
        )}
        {folders.data && me && (
          <Menu title="Project" trigger={(t) => <Button variant="ghost" dense trailing={ChevronDown} className={pickClass} aria-label="Project: none" disabled={make.isPending} {...t}><PickLabel label="Project">None</PickLabel></Button>}>
            {(close) =>
              folders.data!.length === 0 ? (
                <p className="p-3 text-sm text-muted">No projects yet. Make one on the Scripts page.</p>
              ) : (
                folders.data!.map((f) => (
                  <MenuItem key={f.id} onClick={() => { close(); start("", { folder: f.id }); }}>
                    {f.name}
                  </MenuItem>
                ))
              )
            }
          </Menu>
        )}
        <ShapeChip />
        {languages.data && (
          <Menu title="Language" trigger={(t) => <Button variant="ghost" dense trailing={ChevronDown} className={pickClass} aria-label={`Language: ${langName(lang)}`} disabled={make.isPending} {...t}><PickLabel label="Language">{langName(lang)}</PickLabel></Button>}>
            {(close) =>
              picks.map((l) => (
                <MenuItem key={l.id} onClick={() => { close(); start("", { language: l.id }); }}>
                  {l.name}{l.id === lang ? " ✓" : ""}
                </MenuItem>
              ))
            }
          </Menu>
        )}
      </SettingsRow>
      {picking && looks.data && <LookPicker current={look} looks={looks.data} busy={make.isPending ? look : null} error={null} onPick={(l) => { setPicking(false); start("", { look: l.id }); }} onClose={() => setPicking(false)} />}
      <div className="p-4 sm:p-8">
        {kind === "song" ? (
          // A song's first box stays the Song step's own, so the swap between them can't be seen (Song takes are a separate board).
          <div className="max-w-[680px] space-y-3">
            <TextArea {...LYRICS_BOX} autoFocus onChange={(e) => type(e.target.value)} />
            {make.isError && <p role="alert" className={errorClass}>{make.error.message} Type again to try again.</p>}
          </div>
        ) : (
          <ScriptBox
            label="Write or paste the script"
            placeholder={"BO: Is that… salmon?\nOWNER: Only the best for you."}
            words=""
            autoFocus
            onChange={(e) => type(e.target.value)}
            note={make.isError ? <span role="alert" className={errorClass}>{make.error.message} Type again to try again.</span> : "Nothing is saved until you type or pick a setting. Lines with a NAME: are dialogue."}
          />
        )}
      </div>
    </main>
  );
}

/** Import a reel starts from a link or a video, not words, so it keeps its own page. */
export function ImportReelLink({ brandId }: { brandId: number }) {
  return (
    <Link to={`/b/${brandId}/scripts/import`} className={`${buttonClass("secondary")} shrink-0 whitespace-nowrap`}>
      Import a reel
    </Link>
  );
}

import { Fragment, useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import { DraftsPanel } from "./Drafts";
import { EnhanceBar, MarkLine, type EnhanceState } from "./Enhance";
import { useToast } from "../toast";
import { Pencil, Upload, History as Versions, FileText } from "lucide-react";
import { Banner, Button, Card, Menu, MenuItem, buttonClass } from "../components";
import { errorText as errorClass, input } from "../ui";

const SOURCE = { paste: "pasted", upload: "uploaded", draft: "written by Claude", enhance: "enhanced" } as Record<string, string>;
const when = (iso: string) => {
  const d = new Date(iso);
  const today = d.toDateString() === new Date().toDateString();
  return `${today ? "Today" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" })} ${d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
};

/** The working (newest) script, or null when there is none yet. */
export function useLatestScript(projectId: number) {
  return useQuery({
    queryKey: ["script", projectId],
    queryFn: async () => {
      const { data, response } = await api.GET("/projects/{project_id}/script", { params: { path: { project_id: projectId } } });
      if (response.status === 404) return null;
      if (!data) throw new Error("load");
      return data;
    },
  });
}

/** The script: paste it or upload a document. Every save is a new numbered version. */
export function ScriptTab({ projectId, enhance, highlight, onLineClick, used = 0, budget = Infinity }: { projectId: number; enhance: EnhanceState; highlight?: number[]; onLineClick?: (line: number) => void; used?: number; budget?: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const path = { project_id: projectId };
  const [editing, setEditing] = useState<string | null>(null);
  const [viewing, setViewing] = useState<number | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const latest = useLatestScript(projectId);
  const versions = useQuery({
    queryKey: ["script", projectId, "versions"],
    enabled: showHistory,
    queryFn: async () => (await api.GET("/projects/{project_id}/script/versions", { params: { path } })).data ?? [],
  });
  const old = useQuery({
    queryKey: ["script", projectId, "version", viewing],
    enabled: viewing !== null && viewing !== latest.data?.version,
    queryFn: async () =>
      (await api.GET("/projects/{project_id}/script/versions/{version}", { params: { path: { ...path, version: viewing! } } })).data ?? null,
  });
  const saved = () => {
    setEditing(null);
    setViewing(null);
    return queryClient.invalidateQueries({ queryKey: ["script", projectId] });
  };
  const put = async (text: string) => {
    const { data, error } = await api.PUT("/projects/{project_id}/script", { params: { path }, body: { text } });
    if (!data) throw new Error(errorText(error));
    return data;
  };
  const save = useMutation({
    mutationFn: async (text: string) => {
      const before = latest.data?.text;
      await put(text);
      return before;
    },
    onSuccess: async (before) => {
      await saved();
      if (before !== undefined) {
        toast("Saved.", async () => {
          await put(before);
          await saved();
        });
      }
    },
  });
  // Restoring an old version saves its words as the next version; Undo saves the words we had before.
  const restore = useMutation({
    mutationFn: async (version: number) => {
      const { data } = await api.GET("/projects/{project_id}/script/versions/{version}", { params: { path: { ...path, version } } });
      if (!data) throw new Error("Could not load that version.");
      const before = latest.data?.text ?? "";
      await put(data.text);
      return { before };
    },
    onSuccess: async ({ before }) => {
      await saved();
      toast("Restored an earlier version.", async () => {
        await put(before);
        await saved();
      });
    },
  });
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("upload", file);
      await must(api.POST("/projects/{project_id}/script/upload", { params: { path }, body: { upload: file as unknown as string }, bodySerializer: () => form }));
    },
    onSuccess: saved,
  });

  if (latest.isPending) return <p className="text-muted">Loading…</p>;
  if (latest.isError) return <p role="alert" className={errorClass}>Could not load the script. Try again.</p>;

  const current = latest.data;
  const viewingOld = viewing !== null && viewing !== current?.version;
  const shown = viewingOld ? old.data : current;
  const uploadButton = (
    <label className={`${buttonClass("secondary")} cursor-pointer focus-within:outline focus-within:outline-2 focus-within:outline-accent`}>
      <Upload size={20} strokeWidth={1.75} aria-hidden />
      {current ? "Upload a new version" : "Upload a file"}
      <input type="file" accept=".txt,.docx,.pdf" className="sr-only" aria-label="Script file" onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
    </label>
  );
  const problem = save.error ?? upload.error ?? restore.error;

  if (!current && editing === null) {
    return (
      <div className="space-y-4">
        <DraftsPanel projectId={projectId} used={used} budget={budget}>
          <Card className="space-y-3">
            <h2 className="flex items-center gap-2 font-display text-md font-bold">
              <FileText size={20} strokeWidth={1.75} aria-hidden />
              Upload your own
            </h2>
            <p className="text-sm text-muted">A .txt, .docx or .pdf file, or paste it in. Every save is kept.</p>
            <div className="flex flex-wrap items-center gap-2">
              {uploadButton}
              <Button variant="ghost" onClick={() => setEditing("")}>
                Paste it in
              </Button>
            </div>
            {upload.isPending && <p className="text-sm text-muted">Reading the document…</p>}
            {problem && <p role="alert" className={errorClass}>{problem.message}</p>}
          </Card>
        </DraftsPanel>
      </div>
    );
  }
  if (editing !== null) {
    return (
      <Card className="space-y-3">
        <label className="block text-sm">
          <span className="font-medium">Your script</span>
          <textarea className={`${input} font-script`} rows={14} maxLength={50000} value={editing} onChange={(e) => setEditing(e.target.value)} placeholder="Paste your script here" />
        </label>
        {problem && <p role="alert" className={errorClass}>{problem.message}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <Button busy={save.isPending} disabled={!editing.trim()} onClick={() => save.mutate(editing)}>
            Save script
          </Button>
          <Button variant="ghost" onClick={() => setEditing(null)}>
            Cancel
          </Button>
        </div>
      </Card>
    );
  }
  if (!current) return null;

  return (
    <section className="space-y-3" aria-label="Script">
      <div className="flex flex-wrap items-center gap-2">
        {viewingOld ? (
          <Banner tone="warning" title="You're looking at an older version." action={<span className="flex flex-wrap gap-2"><Button variant="secondary" busy={restore.isPending} onClick={() => restore.mutate(viewing!)}>Restore this version</Button><Button variant="ghost" onClick={() => setViewing(null)}>Back to the latest</Button></span>} />
        ) : (
          <>
            <Button variant="secondary" icon={Pencil} onClick={() => setEditing(current.text)}>
              Edit
            </Button>
            {uploadButton}
          </>
        )}
        <Menu title="Versions" trigger={(t) => <Button variant="secondary" icon={Versions} {...t} aria-label="Versions" onClick={() => { setShowHistory(true); t.onClick(); }}>Versions</Button>}>
          {(close) =>
            (versions.data ?? []).map((v) => (
              <MenuItem
                key={v.version}
                checked={(viewing ?? current.version) === v.version}
                onClick={() => {
                  setViewing(v.version === current.version ? null : v.version);
                  close();
                }}
              >
                {when(v.created_at)} · {SOURCE[v.source] ?? v.source} · {v.words} words
              </MenuItem>
            ))
          }
        </Menu>
        <span className="ml-auto text-sm text-muted">
          {shown?.words} words · {SOURCE[shown?.source ?? ""] ?? shown?.source}
          {shown && shown.version === current.version && " · Saved"}
        </span>
      </div>
      {problem && <p role="alert" className={errorClass}>{problem.message}</p>}
      {upload.isPending && <p className="text-sm text-muted">Reading the document…</p>}
      {shown?.version === current.version && <EnhanceBar e={enhance} />}
      <ScriptText
        text={shown?.text ?? ""}
        highlight={shown?.version === current.version ? highlight : undefined}
        onLineClick={shown?.version === current.version ? onLineClick : undefined}
        around={
          shown?.version === current.version
            ? (line, where) => enhance.shown.filter((m) => m.line === line && (m.placement === "before") === (where === "before")).map((m) => <MarkLine key={m.id} mark={m} e={enhance} />)
            : undefined
        }
      />
    </section>
  );
}

/** Line-numbered, in the script font, wrapping at about 64 characters. The words are never altered.
 *  `around` can put other lines (Enhance direction notes) before or after a script line. */
const DIRECTION = /^\s*\[(Camera|Movement|Reaction|Brand screen)\]\s*/;

export function ScriptText({ text, around, highlight = [], onLineClick }: { text: string; around?: (line: number, where: "before" | "after") => ReactNode; highlight?: number[]; onLineClick?: (line: number) => void }) {
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
              <li className={`grid grid-cols-[2.5rem_1fr] items-baseline gap-2 ${highlight.includes(i + 1) ? "bg-accent-soft" : ""}`} data-direction={tag ? tag[1] : undefined} data-hl={highlight.includes(i + 1) || undefined}>
                {onLineClick ? (
                  <button type="button" className="text-right text-xs text-faint underline" aria-label={`Show line ${i + 1} in the breakdown`} onClick={() => onLineClick(i + 1)}>
                    {i + 1}
                  </button>
                ) : (
                  <span className="select-none text-right text-xs text-faint" aria-hidden>
                    {i + 1}
                  </span>
                )}
                {tag ? (
                  <span className="ml-4 flex flex-wrap items-baseline gap-x-3 text-muted sm:ml-8">
                    <span className="whitespace-pre-wrap [overflow-wrap:anywhere]">
                      {tag[1] === "Brand screen" ? "★ " : "▸ "}
                      {line.slice(tag[0].length)}
                    </span>
                    <span className="font-sans text-xs">{tag[1]}</span>
                  </span>
                ) : (
                  <span className="whitespace-pre-wrap [overflow-wrap:anywhere]">{line || "\u00a0"}</span>
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

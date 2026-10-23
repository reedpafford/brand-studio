import { Fragment, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import { EnhanceBar, MarkLine, Notes, useEnhance } from "./Enhance";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText } from "../ui";

const SOURCE = { paste: "pasted", upload: "uploaded", draft: "written by Claude", enhance: "enhanced" } as Record<string, string>;
const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** The script: paste it or upload a document. Every save is a new numbered version. */
export function ScriptTab({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const [editing, setEditing] = useState<string | null>(null);
  const [viewing, setViewing] = useState<number | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const latest = useQuery({
    queryKey: ["script", projectId],
    queryFn: async () => {
      const { data, response } = await api.GET("/projects/{project_id}/script", { params: { path } });
      if (response.status === 404) return null;
      if (!data) throw new Error("load");
      return data;
    },
  });
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
  const save = useMutation({
    mutationFn: async (text: string) => {
      const { error, response } = await api.PUT("/projects/{project_id}/script", { params: { path }, body: { text } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: saved,
  });
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("upload", file);
      await must(api.POST("/projects/{project_id}/script/upload", { params: { path }, body: { upload: file as unknown as string }, bodySerializer: () => form }));
    },
    onSuccess: saved,
  });

  const enhance = useEnhance(projectId, latest.data?.version);

  if (latest.isPending) return <p className="text-muted">Loading…</p>;
  if (latest.isError) return <p role="alert" className={errorClass}>Could not load the script. Try again.</p>;

  const current = latest.data;
  const shown = viewing !== null && viewing !== current?.version ? old.data : current;
  const uploadButton = (
    <label className={`inline-block cursor-pointer ${btnSecondary}`}>
      {current ? "Upload a new version" : "Upload a document"}
      <input type="file" accept=".txt,.docx,.pdf" className="sr-only" aria-label="Script file" onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
    </label>
  );
  const problem = save.error ?? upload.error;

  if (!current || editing !== null) {
    return (
      <section className={`${card} space-y-3`} aria-label="Script">
        {!current && (
          <>
            <p className="text-[length:var(--text-xl)] font-semibold">No script yet.</p>
            <p className="text-muted">Paste your script, or upload a .txt, .docx or .pdf. Every save is kept as a version.</p>
          </>
        )}
        <label className="block text-sm">
          <span className="font-medium">Your script</span>
          <textarea
            className={`${input} font-script`}
            rows={14}
            maxLength={50000}
            value={editing ?? ""}
            onChange={(e) => setEditing(e.target.value)}
            placeholder="Paste your script here"
          />
        </label>
        {problem && <p role="alert" className={errorClass}>{problem.message}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <button className={btnPrimary} disabled={save.isPending || !(editing ?? "").trim()} onClick={() => save.mutate(editing ?? "")}>
            {current ? "Save as a new version" : "Save script"}
          </button>
          {current && (
            <button className={btnSecondary} onClick={() => setEditing(null)}>
              Cancel
            </button>
          )}
          {!current && uploadButton}
          {upload.isPending && <span className="text-muted">Reading the document…</span>}
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-3" aria-label="Script">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted">
          v{shown?.version} · {shown?.words} words · {SOURCE[shown?.source ?? ""] ?? shown?.source}
          {shown && shown.version === current.version && " · saved"}
        </span>
        <span className="ml-auto flex flex-wrap gap-2">
          <button className={btnSecondary} onClick={() => setEditing(current.text)}>
            Edit
          </button>
          {uploadButton}
          <button className={btnSecondary} aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}>
            History
          </button>
        </span>
      </div>
      {viewing !== null && viewing !== current.version && (
        <p className="text-sm text-warning">
          You are looking at version {viewing}.{" "}
          <button className={linkText} onClick={() => setViewing(null)}>
            Back to the latest
          </button>
        </p>
      )}
      {problem && <p role="alert" className={errorClass}>{problem.message}</p>}
      {upload.isPending && <p className="text-sm text-muted">Reading the document…</p>}
      {showHistory && (
        <ul className="divide-y divide-border rounded-md border border-border bg-surface text-sm" aria-label="Script versions">
          {versions.data?.map((v) => (
            <li key={v.version} className="flex flex-wrap items-center gap-3 px-3 py-2">
              <span className="flex-1">
                v{v.version} · {day(v.created_at)} · {SOURCE[v.source] ?? v.source} · {v.words} words
              </span>
              {v.version !== current.version && (
                <>
                  <button className={linkText} aria-label={`View v${v.version}`} onClick={() => setViewing(v.version)}>
                    View
                  </button>
                  <button
                    className={linkText}
                    aria-label={`Restore v${v.version}`}
                    onClick={async () => {
                      const { data } = await api.GET("/projects/{project_id}/script/versions/{version}", { params: { path: { ...path, version: v.version } } });
                      if (data) save.mutate(data.text);
                    }}
                  >
                    Restore
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {shown?.version === current.version && <EnhanceBar e={enhance} />}
      <ScriptText
        text={shown?.text ?? ""}
        around={
          shown?.version === current.version
            ? (line, where) => enhance.marks.filter((m) => m.line === line && (m.placement === "before") === (where === "before")).map((m) => <MarkLine key={m.id} mark={m} e={enhance} />)
            : undefined
        }
      />
      {shown?.version === current.version && <Notes e={enhance} version={current.version} />}
    </section>
  );
}

/** Line-numbered, in the script font, wrapping at about 64 characters. The words are never altered.
 *  `around` can put other lines (Enhance direction notes) before or after a script line. */
export function ScriptText({ text, around }: { text: string; around?: (line: number, where: "before" | "after") => ReactNode }) {
  return (
    <div className="max-w-[72ch] rounded-md border border-border bg-surface p-4 font-script leading-[1.6]">
      <ol aria-label="Script text">
        {text.split("\n").map((line, i) => (
          <Fragment key={i}>
            {around?.(i + 1, "before")}
            <li className="grid grid-cols-[2.5rem_1fr] gap-2">
              <span className="select-none text-right text-xs text-faint" aria-hidden>
                {i + 1}
              </span>
              <span className="whitespace-pre-wrap break-words">{line || "\u00a0"}</span>
            </li>
            {around?.(i + 1, "after")}
          </Fragment>
        ))}
      </ol>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Wand2 } from "lucide-react";
import { api, errorText } from "../api/client";
import { Button, TextArea } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

/** What the server keeps of the last note on a still or a clip. */
export type ChangeState = { note: string; status: "changing" | "done" | "unchanged" | "failed"; before?: string; after?: string; unchanged?: boolean; error?: string } | null;

type Part = { text: string; kind: "same" | "gone" | "new" };

/** Word by word: what stayed, what the note removed, what it added. */
function diff(before: string, after: string): Part[] {
  const a = before.split(/\s+/).filter(Boolean);
  const b = after.split(/\s+/).filter(Boolean);
  const n = a.length;
  const m = b.length;
  const len = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) len[i][j] = a[i] === b[j] ? len[i + 1][j + 1] + 1 : Math.max(len[i + 1][j], len[i][j + 1]);
  const out: Part[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ text: a[i++], kind: "same" });
      j++;
    } else if (len[i + 1][j] >= len[i][j + 1]) out.push({ text: a[i++], kind: "gone" });
    else out.push({ text: b[j++], kind: "new" });
  }
  while (i < n) out.push({ text: a[i++], kind: "gone" });
  while (j < m) out.push({ text: b[j++], kind: "new" });
  return out;
}

/** The changed words with about five around each, at most three snippets: [before parts, after parts]. */
export function changedSnippets(before: string, after: string, around = 5, most = 3): { before: Part[]; after: Part[] }[] {
  const parts = diff(before, after);
  const keep = new Array<boolean>(parts.length).fill(false);
  parts.forEach((p, i) => {
    if (p.kind === "same") return;
    for (let k = Math.max(0, i - around); k <= Math.min(parts.length - 1, i + around); k++) keep[k] = true;
  });
  const groups: Part[][] = [];
  parts.forEach((p, i) => {
    if (!keep[i]) return;
    if (i === 0 || !keep[i - 1]) groups.push([]);
    groups[groups.length - 1].push(p);
  });
  return groups.slice(0, most).map((g) => ({ before: g.filter((p) => p.kind !== "new"), after: g.filter((p) => p.kind !== "gone") }));
}

const Words = ({ parts }: { parts: Part[] }) => (
  <>
    {parts.map((p, i) =>
      p.kind === "gone" ? (
        <del key={i} className="text-danger">{p.text} </del>
      ) : p.kind === "new" ? (
        <strong key={i} className="bg-success-soft font-semibold">{p.text} </strong>
      ) : (
        <span key={i}>{p.text} </span>
      ),
    )}
  </>
);

/** "Change this…": say in plain words what should change; the prompt is rewritten and the still or take is made again. */
export function ChangeBox(props: {
  kind: "frame" | "clip";
  projectId: number;
  /** The frame's or the clip row's id. */
  id: number;
  change: ChangeState;
  /** Why it can't be pressed right now (still being made, made for an older breakdown), or null. */
  hold: string | null;
  /** The allowance/budget stop for a price, or null. */
  stopFor: (cost: number | undefined) => string | null;
  /** Puts the earlier still or take back (with its prompt). Free. */
  onUndo?: () => void;
  label: string;
}) {
  const { kind, projectId, id, change } = props;
  const queryClient = useQueryClient();
  const toast = useToast();
  const [note, setNote] = useState("");
  const [whole, setWhole] = useState(false);
  const changing = change?.status === "changing";
  const price = useQuery({
    queryKey: ["change-price", kind, projectId, id],
    queryFn: async () =>
      (kind === "frame"
        ? await api.GET("/projects/{project_id}/storyboard/frames/{frame_id}/change", { params: { path: { project_id: projectId, frame_id: id } } })
        : await api.GET("/projects/{project_id}/clips/{clip_id}/change", { params: { path: { project_id: projectId, clip_id: id } } })
      ).data?.credits ?? null,
  });
  const credits = price.data ?? undefined;
  const press = useMutation({
    mutationFn: async (text: string) => {
      const { error, response } =
        kind === "frame"
          ? await api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/change", { params: { path: { project_id: projectId, frame_id: id } }, body: { note: text } })
          : await api.POST("/projects/{project_id}/clips/{clip_id}/change", { params: { path: { project_id: projectId, clip_id: id } }, body: { note: text } });
      if (!response.ok) throw Object.assign(new Error(errorText(error)), { status: response.status });
    },
    onSuccess: () => {
      setNote("");
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: [kind === "frame" ? "storyboard" : "project-clips", projectId] });
    },
  });
  // The change has just landed: say so, with the way back.
  const was = useRef(change?.status);
  useEffect(() => {
    if (was.current === "changing" && change?.status === "done") {
      toast("Changed. The earlier one is kept.", props.onUndo);
      void queryClient.invalidateQueries({ queryKey: ["change-price", kind, projectId, id] });
    }
    was.current = change?.status;
  }, [change?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const reason = changing ? null : !note.trim() ? "Say what should change" : props.hold ?? props.stopFor(credits);
  // The server says in its own words when a note touches what is said; the note stays so it can be edited.
  const said = press.error && (press.error as Error & { status?: number }).status === 422;
  const snippets = change && change.status === "done" && change.before !== undefined && change.after !== undefined ? changedSnippets(change.before, change.after) : [];
  return (
    <div className="space-y-2">
      <TextArea label="Change this…" rows={2} maxLength={500} placeholder="What should change?" value={changing ? change!.note : note} readOnly={changing} onChange={(e) => { setNote(e.target.value); press.reset(); }} aria-label={`Change this… ${props.label}`} />
      <Button variant="secondary" icon={Wand2} busy={changing || press.isPending} price={changing ? undefined : credits} reason={reason} disabled={!changing && !!reason} onClick={() => press.mutate(note.trim())}>
        {changing ? "Changing…" : "Change it"}
      </Button>
      {press.isError && (
        <p role="alert" className={said ? "text-sm text-warning" : errorClass}>
          {press.error.message}
          {said && " To change the words, edit the script."}
        </p>
      )}
      {change?.status === "unchanged" && <p className="text-sm text-muted">Your note didn't change the prompt. Try saying it another way.</p>}
      {change?.status === "failed" && <p role="alert" className={errorClass}>{change.error || "The change didn't finish. Credits for it were returned."}</p>}
      {snippets.length > 0 && (
        <div className="space-y-1 text-sm" aria-label="What your note changed">
          <p className="text-muted">What your note changed</p>
          {snippets.map((s, i) => (
            <p key={i}>
              <span className="font-medium">Before: </span>
              <Words parts={s.before} />
              <br />
              <span className="font-medium">After: </span>
              <Words parts={s.after} />
            </p>
          ))}
          <Button variant="ghost" dense onClick={() => setWhole(!whole)} aria-expanded={whole}>
            {whole ? "Hide the whole prompt" : "Show the whole prompt"}
          </Button>
          {whole && <p className="whitespace-pre-wrap rounded-md bg-surface-2 p-2">{change!.after}</p>}
        </div>
      )}
    </div>
  );
}

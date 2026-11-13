import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { Dialog } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

export type VideoTarget = { id: number; name: string; letter?: string; creditsUsed: number; released?: boolean };

/** Reed on any video; an editor on the ones they made. */
export function useMayManageVideo() {
  const { data: me } = useMe();
  return (v: { created_by_id: number | null }) => me?.role === "owner" || (!!me && v.created_by_id === me.id);
}

const STOPS = "Anything still being made stops and isn't brought back.";
/** What archiving a video does, said before it is done. */
export const ARCHIVES = `It leaves the lists. Its clips and downloads are kept, and you can restore it. ${STOPS}`;

/** Release a started version (back to Ready to make) or archive a video, each after a confirm and with Undo. Render `dialog` on the page, or
 *  draw the confirm from `asking` (what is asked, and its yes and no). `reread`: what else to read again after each (a
 *  list of videos it is pressed from). */
export function useVideoActions(onGone?: (kind: "release" | "archive") => void, reread?: () => unknown) {
  const [ask, setAsk] = useState<{ kind: "release" | "archive"; target: VideoTarget } | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
  const refresh = () => Promise.all([...["projects", "production", "scripts", "project"].map((k) => queryClient.invalidateQueries({ queryKey: [k] })), reread?.()]);
  const close = () => (setAsk(null), setProblem(null));

  const undo = (t: VideoTarget) => async () => {
    const { error, response } = await api.POST("/projects/{project_id}/restore", { params: { path: { project_id: t.id } } });
    if (!response.ok) return toast(errorText(error) || `Couldn't bring "${t.name}" back.`, undefined, "error");
    await refresh();
    toast(`Brought back "${t.name}".`);
  };
  const confirm = async () => {
    if (!ask) return;
    const { kind, target: t } = ask;
    setBusy(true);
    setProblem(null);
    const { error, response } = await api.POST(kind === "release" ? "/projects/{project_id}/release" : "/projects/{project_id}/archive", { params: { path: { project_id: t.id } } });
    setBusy(false);
    if (!response.ok) return setProblem(errorText(error));
    close();
    await refresh();
    toast(kind === "release" ? `${t.letter ? `Version ${t.letter}` : "The version"} is ready to make again.` : `Archived "${t.name}".`, undo(t));
    onGone?.(kind);
  };
  const restore = async (t: VideoTarget) => {
    const { error, response } = await api.POST("/projects/{project_id}/restore", { params: { path: { project_id: t.id } } });
    if (!response.ok) return toast(errorText(error), undefined, "error");
    await refresh();
    // Undo puts it back as it was: released again (its version back to Ready to make) or archived again. Free.
    toast(`Brought back "${t.name}".`, async () => {
      const { error, response } = await api.POST(t.released ? "/projects/{project_id}/release" : "/projects/{project_id}/archive", { params: { path: { project_id: t.id } } });
      if (!response.ok) return toast(errorText(error) || `Couldn't put "${t.name}" back.`, undefined, "error");
      await refresh();
      toast(t.released ? `${t.letter ? `Version ${t.letter}` : "The version"} is ready to make again.` : `Archived "${t.name}".`, undo(t));
    });
  };
  const dialog = ask && (
    <Dialog
      title={ask.kind === "release" ? (ask.target.letter ? `Release version ${ask.target.letter}?` : "Release this version?") : `Archive "${ask.target.name}"?`}
      cancelLabel={ask.kind === "release" ? "Keep making it" : "Keep it"}
      actionLabel={ask.kind === "release" ? "Release" : "Archive"}
      danger
      busy={busy}
      onCancel={close}
      onConfirm={() => void confirm()}
    >
      {ask.kind === "release"
        ? `It goes back to Ready to make, so it can be started fresh. This video and its clips are archived, not deleted.${ask.target.creditsUsed > 0 ? ` The ${Math.round(ask.target.creditsUsed)} credits already used stay used.` : ""} ${STOPS}`
        : ARCHIVES}
      {problem && <p role="alert" className={`mt-2 ${errorClass}`}>Couldn't do that. Nothing changed. {problem}</p>}
    </Dialog>
  );
  return { restore, release: (t: VideoTarget) => setAsk({ kind: "release", target: t }), archive: (t: VideoTarget) => setAsk({ kind: "archive", target: t }), dialog, asking: ask && { ...ask, busy, problem, yes: () => void confirm(), no: close } };
}

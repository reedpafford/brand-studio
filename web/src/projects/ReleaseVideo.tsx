import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Archive, Ellipsis, Undo2 } from "lucide-react";
import createClient from "openapi-fetch";
import { errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { Dialog, Menu, MenuItem } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

export type VideoTarget = { id: number; name: string; letter?: string; creditsUsed: number };

// The release, archive and restore routes, until the server's schema has them (then these go and `api` is used).
type Post = { post: { parameters: { path: { project_id: number } }; responses: { 200: { content: never }; 204: { content: never } } } };
type Paths = { "/projects/{project_id}/release": Post; "/projects/{project_id}/archive": Post; "/projects/{project_id}/restore": Post };
const videos = createClient<Paths>({ baseUrl: `${location.origin}/api`, credentials: "include", fetch: (req) => fetch(req) });

/** Reed on any video; an editor on the ones they made. */
export function useMayManageVideo() {
  const { data: me } = useMe();
  return (v: { created_by_id: number | null }) => me?.role === "owner" || (!!me && v.created_by_id === me.id);
}

/** Release a started version (back to Ready to make) or archive a video, each after a confirm and with Undo. Render `dialog` on the page. */
export function useVideoActions(onGone?: () => void) {
  const [ask, setAsk] = useState<{ kind: "release" | "archive"; target: VideoTarget } | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
  const refresh = () => Promise.all(["projects", "production", "scripts", "project"].map((k) => queryClient.invalidateQueries({ queryKey: [k] })));
  const close = () => (setAsk(null), setProblem(null));

  const undo = (t: VideoTarget) => async () => {
    const { error, response } = await videos.POST("/projects/{project_id}/restore", { params: { path: { project_id: t.id } } });
    if (!response.ok) return toast(errorText(error) || `Couldn't bring "${t.name}" back.`, undefined, "error");
    await refresh();
    toast(`Brought back "${t.name}".`);
  };
  const confirm = async () => {
    if (!ask) return;
    const { kind, target: t } = ask;
    setBusy(true);
    setProblem(null);
    const { error, response } = await videos.POST(kind === "release" ? "/projects/{project_id}/release" : "/projects/{project_id}/archive", { params: { path: { project_id: t.id } } });
    setBusy(false);
    if (!response.ok) return setProblem(errorText(error));
    close();
    await refresh();
    toast(kind === "release" ? `${t.letter ? `Version ${t.letter}` : "The version"} is ready to make again.` : `Archived "${t.name}".`, undo(t));
    onGone?.();
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
        ? `It goes back to Ready to make, so it can be started fresh. This video and its clips are archived, not deleted.${ask.target.creditsUsed > 0 ? ` The ${Math.round(ask.target.creditsUsed)} credits already used stay used.` : ""}`
        : "It leaves the lists. Its clips and downloads are kept, and you can restore it."}
      {problem && <p role="alert" className={`mt-2 ${errorClass}`}>Couldn't do that. Nothing changed. {problem}</p>}
    </Dialog>
  );
  return { release: (t: VideoTarget) => setAsk({ kind: "release", target: t }), archive: (t: VideoTarget) => setAsk({ kind: "archive", target: t }), dialog };
}

/** The "..." menu of a video: Release this version and/or Archive video. */
export function VideoMenu({ title, onRelease, onArchive }: { title: string; onRelease?: () => void; onArchive?: () => void }) {
  if (!onRelease && !onArchive) return null;
  const item = (Icon: typeof Undo2, label: string, run: () => void, close: () => void) => (
    <MenuItem
      key={label}
      onClick={() => {
        close();
        run();
      }}
    >
      <Icon size={20} strokeWidth={1.75} aria-hidden />
      {label}
    </MenuItem>
  );
  return (
    <Menu
      title={`More for ${title}`}
      align="right"
      trigger={(p) => (
        <button type="button" {...p} aria-label={`More for ${title}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-9">
          <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
        </button>
      )}
    >
      {(close) => (
        <>
          {onRelease && item(Undo2, "Release this version", onRelease, close)}
          {onArchive && item(Archive, "Archive video", onArchive, close)}
        </>
      )}
    </Menu>
  );
}

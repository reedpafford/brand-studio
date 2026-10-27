import { useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ellipsis, Lock, Merge, Trash2, Users, Wand2 } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import type { components } from "../api/schema";
import { Badge, Button, Card, Menu, MenuItem, TextArea, useToast, Select, wholeCredits } from "../components";
import { errorText as errorClass } from "../ui";
import { lookFitNote, useSheetPrice } from "../library/SheetPanel";
import { RoleFacts } from "./RoleFacts";

type Asset = components["schemas"]["AssetOut"];

const STATUS: Record<
  string,
  { tone: "success" | "warning" | "neutral"; text: string }
> = {
  approved: { tone: "success", text: "Approved" },
  needs_approval: { tone: "warning", text: "Needs your approval" },
  drawing: { tone: "neutral", text: "Drawing…" },
  waiting_for_owner: { tone: "neutral", text: "Not started" },
  none: { tone: "warning", text: "Needs a look" },
  missing: { tone: "warning", text: "Needs a look" },
};

export const InShots = ({ n }: { n: number }) => (
  <p className="text-sm text-muted">
    In {n} shot{n === 1 ? "" : "s"}
  </p>
);

export function AssetCard({
  asset,
  projectId,
  brandId,
  stopFor,
  onMerge,
  mergeAlone,
  sameAs,
}: {
  asset: Asset;
  projectId: number;
  brandId: number;
  stopFor: (cost: number | undefined) => string | null;
  /** Merge into… for a role, when the video has another role; and the "may be the same as" badge. */
  onMerge?: () => void;
  /** The only role on the video: Merge into… is shown disabled, with why. */
  mergeAlone?: boolean;
  sameAs?: ReactNode;
}) {
  const kind: "place" | "character" =
    asset.kind === "place" ? "place" : "character";
  const queryClient = useQueryClient();
  const toast = useToast();
  const here = useLocation();
  const [pick, setPick] = useState("");
  const [swapping, setSwapping] = useState(false);
  const id = asset.library_item_id;
  const item = useQuery({
    queryKey: ["library", kind, "item", id],
    enabled: id !== null,
    queryFn: async () =>
      (
        await api.GET("/library/{kind}/{item_id}", {
          params: { path: { kind, item_id: id! } },
        })
      ).data ?? null,
  });
  const characters = useQuery({
    queryKey: ["library", "character", brandId, false],
    enabled:
      asset.ref.startsWith("slot:") || (!asset.locked && kind === "character"),
    queryFn: async () =>
      (
        await api.GET("/library/{kind}", {
          params: { path: { kind: "character" }, query: { brand_id: brandId } },
        })
      ).data ?? [],
  });
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["assets", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["library", kind] }),
      queryClient.invalidateQueries({ queryKey: ["breakdown", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] }),
    ]);
  const choose = useMutation({
    mutationFn: async (itemId: number) => {
      const slot = asset.slot_id ?? Number(asset.ref.split(":")[1]);
      const { response, error } = await api.PUT(
        "/projects/{project_id}/assets/slots/{slot_id}",
        {
          params: { path: { project_id: projectId, slot_id: slot } },
          body: { library_item_id: itemId },
        },
      );
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      setPick("");
      setSwapping(false);
      await refresh();
      // The frames are rewritten for the new cast, and their stills redrawn when the video can pay for it.
      const video = await queryClient.fetchQuery({ queryKey: ["project", projectId], staleTime: 0, queryFn: async () => (await api.GET("/projects/{project_id}", { params: { path: { project_id: projectId } } })).data ?? null });
      const done = (video?.cast_redraw as { redrawn_for_cast?: { count: number; credits: number } } | null | undefined)?.redrawn_for_cast;
      if (done) toast(`Redrew ${done.count} still${done.count === 1 ? "" : "s"} for the new cast · ${wholeCredits(done.credits)} credits.`);
    },
  });
  // No character for this role yet: make a look for this video only from the role and its description, and draw its sheet in the same press.
  const { model, price } = useSheetPrice();
  const slot = asset.slot_id ?? Number(asset.ref.split(":")[1]);
  const makeLook = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.POST("/projects/{project_id}/assets/slots/{slot_id}/make-look", { params: { path: { project_id: projectId, slot_id: slot } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  // A look made for this video (or script) has its own sheet buttons here: Approve, and Change this…
  const own = asset.only_here != null;
  const using = own && asset.own_look_id === asset.library_item_id;
  const notUsed = own && !using;
  const [change, setChange] = useState("");
  const changeBox = useRef<HTMLTextAreaElement>(null);
  const approve = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.POST("/library/{kind}/{item_id}/sheet/approve", { params: { path: { kind, item_id: id! } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      await refresh();
      toast(`${asset.role}'s look approved.`, async () => {
        await api.DELETE("/library/{kind}/{item_id}/sheet/approve", { params: { path: { kind, item_id: id! } } });
        await refresh();
      });
    },
  });
  const redraw = useMutation({
    mutationFn: async (note: string) => {
      const { response, error } = await api.POST("/library/{kind}/{item_id}/sheet", { params: { path: { kind, item_id: id! } }, body: { model_id: model, change: note } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      setChange("");
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      await refresh();
    },
  });
  // Delete this look (it is archived, so Undo brings it back with its sheets). The server refuses while a role still uses it.
  const lookId = using ? id : asset.own_look_id;
  const remove = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.DELETE("/library/{kind}/{item_id}", { params: { path: { kind: "character", item_id: lookId! } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      await refresh();
      toast(`Deleted ${asset.role}'s look.`, async () => {
        await api.POST("/library/{kind}/{item_id}/unarchive", { params: { path: { kind: "character", item_id: lookId! } } });
        await refresh();
      });
    },
  });
  // A look's sheet may get one automatic redo, so the press holds the most it can cost; the usual price is the sheet alone.
  const makeUpTo = asset.look_credits ?? undefined;
  const makeUsual = asset.look_usual_credits ?? price;
  const changeUpTo = item.data?.change_credits || undefined;
  const decline = stopFor(makeUpTo ?? price);
  const drawingNow = asset.sheet_status === "drawing";
  const changeDecline = stopFor(changeUpTo ?? price);
  const changeReason = !change.trim() ? "Say what should change" : drawingNow ? "This one is still being made" : changeDecline;
  const status = STATUS[asset.sheet_status] ?? STATUS.none;
  const sheet = item.data?.sheet_file_id;
  const ratio = kind === "place" ? "16 / 9" : "9 / 16";
  const title = asset.role || asset.name;
  // Its Cast & places character was deleted: the slot is stuck until a look is made or another character is picked.
  const deleted = asset.library_deleted && !asset.locked;
  const others = (characters.data ?? []).filter((c) => c.id !== id).length; // Cast & places characters to pick instead
  // A deleted character also has no id any more, but that role has its own two fixes (Make a look, Pick another).
  const slotLeft =
    asset.ref.startsWith("slot:") && asset.library_item_id === null && !deleted;

  return (
    <section aria-label={title}>
      <Card className="flex gap-4 sm:flex-col">
        <div className="w-24 shrink-0 sm:w-full">
          {sheet ? (
            <img
              src={fileUrl(sheet)}
              alt={`Look of ${title}`}
              className="w-full rounded-md bg-surface-2 object-cover"
              style={{ aspectRatio: ratio }}
            />
          ) : id !== null && item.isPending ? (
            <div
              className="w-full animate-pulse rounded-md bg-surface-2"
              style={{ aspectRatio: ratio }}
            />
          ) : (
            <div
              className="grid w-full place-items-center rounded-md bg-surface-2 text-sm text-muted"
              style={{ aspectRatio: ratio }}
            >
              No look yet
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <p className="font-medium">
            {title}
            {asset.name && asset.name !== title && (
              <span className="text-muted"> · {asset.name}</span>
            )}
          </p>
          {!asset.locked && <RoleFacts facts={asset.facts} />}
          {asset.description && !asset.locked && (
            <p className="line-clamp-2 text-sm text-muted">
              {asset.description}
            </p>
          )}
          {asset.shots > 0 && <InShots n={asset.shots} />}
          <div className="flex flex-wrap gap-2">
            {asset.locked ? (
              <Badge icon={Lock}>Locked</Badge>
            ) : deleted ? (
              <Badge tone="danger">Character deleted</Badge>
            ) : slotLeft ? (
              <Badge tone="warning">Needs a look</Badge>
            ) : (
              <Badge tone={status.tone}>{status.text}</Badge>
            )}
            {using && <Badge>{asset.only_here === "script" ? "This script only" : "This video only"}</Badge>}
          </div>
          {deleted && <p className="text-sm text-muted">The character this role used was deleted from Cast &amp; places.</p>}
          {sameAs}
          {((notUsed && lookId != null && !asset.locked) || onMerge || mergeAlone) && (
            <Menu title="Look actions" trigger={(t) => <Button variant="ghost" dense icon={Ellipsis} aria-label={`More for ${title}`} {...t} />}>
              {(close) => (
                <>
                  {(onMerge || mergeAlone) && (
                    <MenuItem disabled={!onMerge} onClick={() => { close(); onMerge?.(); }}>
                      <Merge size={20} strokeWidth={1.75} aria-hidden />
                      Merge into…
                    </MenuItem>
                  )}
                  {mergeAlone && <p className="px-3 pb-2 text-xs text-muted">There's no other role to merge into.</p>}
                  {notUsed && lookId != null && !asset.locked && (
                    <MenuItem danger onClick={() => { close(); remove.mutate(); }}>
                      <Trash2 size={20} strokeWidth={1.75} aria-hidden />
                      Delete this look
                    </MenuItem>
                  )}
                </>
              )}
            </Menu>
          )}
          {notUsed && (
            <div className="space-y-2">
              <p className="text-sm text-muted">Not used: this {asset.only_here === "script" ? "script" : "video"}'s own look is kept.</p>
              <Button variant="secondary" busy={choose.isPending} onClick={() => choose.mutate(asset.own_look_id!)}>
                Use its own look again
              </Button>
            </div>
          )}
          {!asset.locked &&
            id !== null &&
            asset.slot_id != null &&
            !deleted &&
            !swapping && (
              <Button variant="ghost" onClick={() => setSwapping(true)}>
                Use a different character
              </Button>
            )}
          {!asset.locked && (slotLeft || swapping || deleted) && (
            <div className="space-y-2">
              {(slotLeft || deleted) && kind === "character" && (
                <div className="flex flex-wrap items-start gap-2">
                  <Button
                    variant="secondary"
                    busy={makeLook.isPending}
                    price={makeUpTo ?? price}
                    upTo={makeUpTo !== undefined}
                    usually={makeUsual}
                    reason={decline}
                    disabled={!!decline}
                    onClick={() => makeLook.mutate()}
                  >
                    Make a look
                  </Button>
                  {deleted && !swapping && (
                    <span className="flex flex-wrap items-center gap-2">
                      <Button variant="secondary" icon={Users} disabled={others === 0} reason={others === 0 ? "Cast & places has no other characters yet." : undefined} onClick={() => setSwapping(true)}>
                        Pick another
                      </Button>
                      {others > 0 && <span className="text-sm text-muted">Free</span>}
                    </span>
                  )}
                </div>
              )}
              {(slotLeft || swapping) && others > 0 && (
                <>
                  <Select
                    label="Use a Cast & places character"
                    value={pick}
                    onChange={(e) => setPick(e.target.value)}
                  >
                    <option value="">Choose…</option>
                    {(characters.data ?? [])
                      .filter((c) => c.id !== id)
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                          {c.sheet_status === "approved"
                            ? ""
                            : " · needs a look"}
                        </option>
                      ))}
                  </Select>
                  <Button
                    variant="secondary"
                    busy={choose.isPending}
                    disabled={!pick}
                    reason={pick ? undefined : "Choose a character first"}
                    onClick={() => choose.mutate(Number(pick))}
                  >
                    Use this character
                  </Button>
                </>
              )}
              {swapping && (
                <Button variant="ghost" onClick={() => setSwapping(false)}>
                  Cancel
                </Button>
              )}
            </div>
          )}
          {asset.look_fit && !asset.locked && (
            <div className="space-y-1 rounded-md bg-warning-soft p-2 text-sm" role="note" aria-label={`Look check for ${title}`}>
              <p>{lookFitNote(asset.look_fit)}</p>
              {using && (
                <Button variant="secondary" dense icon={Wand2} onClick={() => { setChange(asset.look_fit!.problem); changeBox.current?.focus(); }}>
                  Fix it with a note
                </Button>
              )}
            </div>
          )}
          {using && !asset.locked && (
            <div className="space-y-2">
              {asset.sheet_status === "needs_approval" && (
                <Button variant="secondary" busy={approve.isPending} onClick={() => approve.mutate()}>
                  Approve
                </Button>
              )}
              <TextArea ref={changeBox} label="Change this…" rows={2} maxLength={500} placeholder="What should change?" value={change} onChange={(e) => setChange(e.target.value)} />
              <Button variant="secondary" icon={Wand2} busy={redraw.isPending} price={changeUpTo ?? price} upTo={changeUpTo !== undefined} usually={item.data?.sheet_usual_credits || price} reason={changeReason} disabled={!!changeReason} onClick={() => redraw.mutate(change.trim())}>
                Change it
              </Button>
            </div>
          )}
          {!asset.locked &&
            id !== null &&
            !own &&
            asset.sheet_status !== "approved" && (
              <Link
                to={`/b/${brandId}/library/${kind === "place" ? "places" : "characters"}/${id}?back=${encodeURIComponent(here.pathname + here.search)}`}
                className="inline-flex min-h-control items-center text-accent-text hover:underline sm:min-h-control-dense"
              >
                Make its look in Cast &amp; places
              </Link>
            )}
          {(choose.error ?? makeLook.error ?? approve.error ?? redraw.error ?? remove.error) && (
            <p role="alert" className={errorClass}>
              {(choose.error ?? makeLook.error ?? approve.error ?? redraw.error ?? remove.error)!.message}
            </p>
          )}
        </div>
      </Card>
    </section>
  );
}

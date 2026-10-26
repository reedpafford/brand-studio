import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Users, Wand2 } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import type { components } from "../api/schema";
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  Field,
  TextArea,
  useToast,
  Select,
  Skeleton,
  wholeCredits,
} from "../components";
import { errorText as errorClass } from "../ui";
import { useMe } from "../auth/useMe";
import { useSheetPrice } from "../library/SheetPanel";
import { useOwnScriptStop } from "./useOwnScriptStop";
import { FlavourPicker, useBriefChoices } from "./BriefPickers";

type Asset = components["schemas"]["AssetOut"];

export function useAssets(projectId: number) {
  return useQuery({
    queryKey: ["assets", projectId],
    refetchInterval: (q) => (q.state.data?.some((a) => a.sheet_status === "drawing") ? 3000 : false),
    queryFn: async () =>
      (
        await api.GET("/projects/{project_id}/assets", {
          params: { path: { project_id: projectId } },
        })
      ).data ?? [],
  });
}

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

const InShots = ({ n }: { n: number }) => (
  <p className="text-sm text-muted">
    In {n} shot{n === 1 ? "" : "s"}
  </p>
);

/** A product or an app screen the shots show: the brand's own picture, nothing to make or approve. */
function PictureCard({ asset }: { asset: Asset }) {
  return (
    <section aria-label={asset.name}>
      <Card className="flex items-center gap-4">
        {asset.file_id != null && (
          <img
            src={fileUrl(asset.file_id)}
            alt=""
            className="size-20 shrink-0 rounded-md bg-surface-2 object-cover"
          />
        )}
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-medium">{asset.name}</p>
          {asset.shots > 0 && <InShots n={asset.shots} />}
        </div>
      </Card>
    </section>
  );
}

function AssetCard({
  asset,
  projectId,
  brandId,
  stopFor,
  canSave,
}: {
  asset: Asset;
  projectId: number;
  brandId: number;
  stopFor: (cost: number | undefined) => string | null;
  canSave: boolean;
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
  const [saving, setSaving] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async (name: string) => {
      const { data, error } = await api.POST("/projects/{project_id}/assets/slots/{slot_id}/save-to-library", { params: { path: { project_id: projectId, slot_id: slot } }, body: { name } });
      if (!data) throw new Error(errorText(error));
      return { copy: data.library_item_id, name };
    },
    onSuccess: async ({ copy, name }) => {
      setSaving(null);
      await refresh();
      toast(`${name} saved to Cast & places.`, async () => {
        await api.DELETE("/library/{kind}/{item_id}", { params: { path: { kind: "character", item_id: copy } } });
        await refresh();
      });
    },
  });
  const decline = stopFor(price);
  const drawingNow = asset.sheet_status === "drawing";
  const changeReason = !change.trim() ? "Say what should change" : drawingNow ? "This one is still being made" : decline;
  const status = STATUS[asset.sheet_status] ?? STATUS.none;
  const sheet = item.data?.sheet_file_id;
  const ratio = kind === "place" ? "16 / 9" : "9 / 16";
  const title = asset.role || asset.name;
  const slotLeft =
    asset.ref.startsWith("slot:") && asset.library_item_id === null;

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
          {asset.description && !asset.locked && (
            <p className="line-clamp-2 text-sm text-muted">
              {asset.description}
            </p>
          )}
          {asset.shots > 0 && <InShots n={asset.shots} />}
          <div className="flex flex-wrap gap-2">
            {asset.locked ? (
              <Badge icon={Lock}>Locked</Badge>
            ) : slotLeft ? (
              <Badge tone="warning">Needs a look</Badge>
            ) : (
              <Badge tone={status.tone}>{status.text}</Badge>
            )}
            {using && <Badge>{asset.only_here === "script" ? "This script only" : "This video only"}</Badge>}
          </div>
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
            !swapping && (
              <Button variant="ghost" onClick={() => setSwapping(true)}>
                Use a different character
              </Button>
            )}
          {!asset.locked && (slotLeft || swapping) && (
            <div className="space-y-2">
              {slotLeft && kind === "character" && (
                <Button
                  variant="secondary"
                  busy={makeLook.isPending}
                  price={price}
                  reason={decline}
                  disabled={!!decline}
                  onClick={() => makeLook.mutate()}
                >
                  Make a look
                </Button>
              )}
              {(characters.data ?? []).filter((c) => c.id !== id).length >
                0 && (
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
          {using && !asset.locked && (
            <div className="space-y-2">
              {asset.sheet_status === "needs_approval" && (
                <Button variant="secondary" busy={approve.isPending} onClick={() => approve.mutate()}>
                  Approve
                </Button>
              )}
              <TextArea label="Change this…" rows={2} maxLength={500} placeholder="What should change?" value={change} onChange={(e) => setChange(e.target.value)} />
              <Button variant="secondary" icon={Wand2} busy={redraw.isPending} price={price} reason={changeReason} disabled={!!changeReason} onClick={() => redraw.mutate(change.trim())}>
                Change it
              </Button>
              {asset.only_here === "video" && canSave && (
                <Button variant="secondary" dense icon={Users} reason={asset.sheet_status === "approved" ? null : "Approve the sheet first"} disabled={asset.sheet_status !== "approved"} onClick={() => setSaving(asset.role)}>
                  Save to Cast &amp; places
                </Button>
              )}
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
          {(choose.error ?? makeLook.error ?? approve.error ?? redraw.error) && (
            <p role="alert" className={errorClass}>
              {(choose.error ?? makeLook.error ?? approve.error ?? redraw.error)!.message}
            </p>
          )}
          {saving !== null && (
            <Dialog title="Save to Cast & places" actionLabel="Save" busy={save.isPending} onCancel={() => { setSaving(null); save.reset(); }} onConfirm={() => save.mutate(saving.trim())}>
              <div className="space-y-2">
                <Field label="Name" value={saving} onChange={(e) => setSaving(e.target.value)} error={save.isError ? save.error.message : null} maxLength={80} />
                <p className="text-sm text-muted">It becomes a normal character any script can use. This video keeps its look either way.</p>
              </div>
            </Dialog>
          )}
        </div>
      </Card>
    </section>
  );
}

/** Everything this video needs on screen, approved before anything is drawn. */
export function AssetsPane({
  projectId,
  brandId,
  variants,
  ownScript,
  used,
  budget,
}: {
  projectId: number;
  brandId: number;
  variants: Record<string, string>;
  ownScript?: boolean;
  used: number;
  budget: number;
}) {
  const assets = useAssets(projectId);
  const stopFor = useOwnScriptStop(ownScript, { used, budget });
  const { data: me } = useMe();
  const limits = useQuery({ queryKey: ["credit-limits"], queryFn: async () => (await api.GET("/credits/limits")).data ?? null });
  // Reed always may save a look to Cast & places; an editor only when Team allows it.
  const canSave = me?.role === "owner" || !!limits.data?.editors_can_save_looks;
  const queryClient = useQueryClient();
  const picks = useBriefChoices(brandId, variants);
  const flavour = useMutation({
    mutationFn: async ([product, variant]: [string, string]) => {
      const { response, error } = await api.PATCH("/projects/{project_id}", {
        params: { path: { project_id: projectId } },
        body: { product_variants: { ...variants, [product]: variant } },
      });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["project", projectId] }),
  });
  if (assets.isPending)
    return (
      <div
        role="status"
        aria-label="Loading"
        className="grid gap-4 lg:grid-cols-3"
      >
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-64" />
        ))}
      </div>
    );
  const list = assets.data ?? [];
  const cast = list.filter((a) => a.kind === "character");
  const places = list.filter((a) => a.kind === "place");
  const products = list.filter((a) => a.kind === "product");
  const screens = list.filter((a) => a.kind === "screen");
  const pictures = (rows: Asset[]) => (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {rows.map((a) => (
        <PictureCard key={a.ref} asset={a} />
      ))}
    </div>
  );
  const grid = (rows: Asset[]) => (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {rows.map((a) => (
        <AssetCard
          key={`${a.kind}-${a.role || a.ref}`}
          asset={a}
          projectId={projectId}
          brandId={brandId}
          stopFor={stopFor}
          canSave={canSave}
        />
      ))}
    </div>
  );
  if (list.length === 0 && picks.products.size === 0)
    return (
      <EmptyState title="Nothing to approve">
        The breakdown uses no characters or places. Go on to the storyboard.
      </EmptyState>
    );
  return (
    <div className="space-y-6">
      {cast.length > 0 && (
        <section aria-label="Cast" className="space-y-3">
          <h3 className="type-section">Cast</h3>
          {grid(cast)}
        </section>
      )}
      {places.length > 0 && (
        <section aria-label="Places" className="space-y-3">
          <h3 className="type-section">Places</h3>
          {grid(places)}
        </section>
      )}
      {(picks.products.size > 0 || products.length > 0) && (
        <section aria-label="Products" className="space-y-3">
          <h3 className="type-section">Products</h3>
          {products.length > 0 && pictures(products)}
          <FlavourPicker
            products={picks.products}
            chosen={picks.chosen}
            onPick={(p, v) => flavour.mutate([p, v])}
          />
          {flavour.error && (
            <p role="alert" className={errorClass}>
              {flavour.error.message}
            </p>
          )}
        </section>
      )}
      {screens.length > 0 && (
        <section aria-label="App screens" className="space-y-3">
          <h3 className="type-section">App screens</h3>
          {pictures(screens)}
        </section>
      )}
    </div>
  );
}

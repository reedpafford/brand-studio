import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Card, EmptyState, Skeleton } from "../components";
import { fileUrl } from "../api/upload";
import { errorText as errorClass } from "../ui";
import { useMe } from "../auth/useMe";
import { useOwnScriptStop } from "./useOwnScriptStop";
import { useApproveAllWith, type ApproveAllResult } from "./ApproveAll";
import { AutoLooks } from "./AutoLooks";
import { useAssetMerge } from "./AssetMerge";
import { FlavourPicker, useBriefChoices } from "./BriefPickers";
import { AssetCard, InShots } from "./AssetCard";

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

/** A product or an app screen the shots show: the brand's own picture, nothing to make or approve. */
export function PictureCard({ asset }: { asset: Asset }) {
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
  const merge = useAssetMerge(projectId, (assets.data ?? []).filter((a) => a.kind === "character"));
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
  // Approve all: the looks made for this video (or script) whose sheet is drawn. Library characters and locked roles are approved elsewhere or already are.
  const roles = (assets.data ?? []).filter((a) => a.kind === "character" && !a.locked && a.sheet_status !== "approved" && (a.only_here != null || a.library_item_id == null));
  const approveAll = useApproveAllWith({
    noun: "look",
    ready: roles.filter((a) => a.only_here != null && a.sheet_status === "needs_approval").length,
    waiting: roles.length,
    press: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/assets/approve-all", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data as ApproveAllResult;
    },
    undo: (ids) => api.POST("/projects/{project_id}/assets/approve-all/undo", { params: { path: { project_id: projectId } }, body: { ids } }),
    refresh: () => Promise.all([["assets", projectId], ["library", "character"], ["breakdown", projectId], ["storyboard", projectId], ["project-clips", projectId]].map((queryKey) => queryClient.invalidateQueries({ queryKey }))), // as a single Approve does
    name: (s) => s.label ?? "",
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
          onMerge={a.kind === "character" && merge.canMerge(a) ? () => merge.start(a) : undefined}
          mergeAlone={a.kind === "character" && merge.alone(a)}
          sameAs={a.kind === "character" ? merge.badge(a) : undefined}
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
      {merge.dialog}
      <AutoLooks projectId={projectId} toApprove={list.some((a) => a.sheet_status === "needs_approval")} />
      {cast.length > 0 && (
        <section aria-label="Cast" className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="type-section">Cast</h3>
            {approveAll.button}
          </div>
          {approveAll.line}
          {merge.note}
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

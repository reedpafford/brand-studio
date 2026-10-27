import { useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useToast } from "../components";
import { MaybeSame, MaybeSameBadge, pairId, type Pair } from "./MaybeSame";
import { MergeRole, mergedText } from "./MergeRole";

type Asset = components["schemas"]["AssetOut"];

const slotOf = (a: Asset) => a.slot_id ?? null;
const nameOf = (a: Asset) => a.role || a.name;
const factsText = (a: Asset) => [a.facts?.age_range, a.facts?.gender, a.facts?.occupation].map((f) => f?.value).filter(Boolean).join(" · ");

/** Merge into… and "These may be the same person" on a video's Assets: this video only, the script's cast stays as it is. */
export function useAssetMerge(projectId: number, cast: Asset[]) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [merging, setMerging] = useState<{ asset: Asset; suggested?: number } | null>(null);
  const [outlined, setOutlined] = useState<string | null>(null);
  const path = { project_id: projectId };
  const roles = cast.filter((a) => slotOf(a) !== null);
  const flags = useQuery({ queryKey: ["assets-maybe-same", projectId], queryFn: async () => (await api.GET("/projects/{project_id}/assets/maybe-same", { params: { path } })).data ?? [] });
  const refresh = () => Promise.all([["assets", projectId], ["assets-maybe-same", projectId], ["breakdown", projectId], ["storyboard", projectId], ["project-clips", projectId]].map((queryKey) => queryClient.invalidateQueries({ queryKey })));
  const bySlot = (id: number) => roles.find((a) => slotOf(a) === id);
  const pairs: Pair[] = (flags.data ?? []).filter((p) => bySlot(p.a_slot_id) && bySlot(p.b_slot_id)).map((p) => ({ a: p.a_slot_id, b: p.b_slot_id, into: p.into_slot_id, why: p.why }));
  const pairsOf = (a: Asset) => pairs.filter((p) => p.a === slotOf(a) || p.b === slotOf(a));
  const nameBySlot = (id: number) => (bySlot(id) ? nameOf(bySlot(id)!) : "");
  const showPair = (p: Pair) => {
    document.getElementById(pairId(p))?.scrollIntoView?.({ block: "center" });
    setOutlined(pairId(p));
    setTimeout(() => setOutlined(null), 1500);
  };

  const undo = async (token: number) => {
    const { error, response } = await api.POST("/projects/{project_id}/assets/merge/undo", { params: { path }, body: { token } });
    if (!response.ok) throw new Error(errorText(error)); // "This can't be undone any more: the shots were changed after the merge."
    await refresh();
  };
  const dialog = merging && (
    <MergeRole
      role={nameOf(merging.asset)}
      roleId={slotOf(merging.asset)!}
      videoOnly
      others={roles.filter((a) => a !== merging.asset).map((a) => ({ id: slotOf(a)!, role: nameOf(a), kind: "", locked: a.locked, facts: factsText(a) }))}
      suggested={merging.suggested}
      adapter={{
        preview: async (into) => {
          const { data, error } = await api.GET("/projects/{project_id}/assets/slots/{slot_id}/merge/preview", { params: { path: { ...path, slot_id: slotOf(merging.asset)! }, query: { into } } });
          if (!data) throw new Error(errorText(error));
          return { ...data.moved, look_unused: data.look_unused };
        },
        merge: async (into) => {
          const { data, error } = await api.POST("/projects/{project_id}/assets/slots/{slot_id}/merge", { params: { path: { ...path, slot_id: slotOf(merging.asset)! } }, body: { into_slot_id: into } });
          if (!data) throw new Error(errorText(error));
          await refresh();
          return { ...data.moved, look_unused: data.look_unused, token: data.token };
        },
      }}
      onMerged={(into, merged) => {
        setMerging(null);
        toast(mergedText(into.role, merged), () => void undo(merged.token!).catch((e: Error) => toast(e.message, undefined, "error")));
      }}
      onClose={() => setMerging(null)}
    />
  );
  return {
    /** Merge into… is offered on a role card when there is another role. */
    canMerge: (a: Asset) => slotOf(a) !== null && roles.length > 1,
    start: (a: Asset) => setMerging({ asset: a }),
    note: <MaybeSame pairs={pairs} name={nameBySlot} outlined={outlined} onMerge={(p) => { const a = bySlot(p.into === p.a ? p.b : p.a); if (a) setMerging({ asset: a, suggested: p.into }); }} />,
    badge: (a: Asset): ReactNode => pairsOf(a).slice(0, 1).map((p) => <MaybeSameBadge key={pairId(p)} other={nameBySlot(p.a === slotOf(a) ? p.b : p.a)} onClick={() => showPair(p)} />),
    dialog,
  };
}

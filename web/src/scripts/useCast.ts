import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";

export type Slot = components["schemas"]["SlotOut"];

/** The roles of a script, shared by every version. */
export function useCast(scriptId: number) {
  return useQuery({
    queryKey: ["script-cast", scriptId],
    queryFn: async () => (await api.GET("/scripts/{script_id}/cast", { params: { path: { script_id: scriptId } } })).data ?? [],
  });
}

/** This brand's characters, with whether they have an approved sheet (a locked look needs one). */
export function useBrandCharacters(brandId: number) {
  return useQuery({
    queryKey: ["library", "character", brandId, false],
    queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind: "character" }, query: { brand_id: brandId } } })).data ?? [],
    refetchInterval: (q) => (q.state.data?.some((c) => c.sheet_status === "drawing") ? 3000 : false), // a sheet being drawn
  });
}

export function useCastActions(scriptId: number) {
  const queryClient = useQueryClient();
  const path = { script_id: scriptId };
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["script-cast", scriptId] }), queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] })]);
  const add = useMutation({
    mutationFn: async (a: { role: string; kind?: "Main" | "Helper" | "Rival" | "Family"; description: string }) => {
      const { data, error } = await api.POST("/scripts/{script_id}/cast", { params: { path }, body: a });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: refresh,
  });
  const edit = useMutation({
    mutationFn: async (a: { id: number; role?: string; kind?: "Main" | "Helper" | "Rival" | "Family"; description?: string }) => {
      const { id, ...body } = a;
      const { error, response } = await api.PATCH("/scripts/{script_id}/cast/{slot_id}", { params: { path: { ...path, slot_id: id } }, body });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: async (id: number) => {
      const { error, response } = await api.DELETE("/scripts/{script_id}/cast/{slot_id}", { params: { path: { ...path, slot_id: id } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  const lock = useMutation({
    mutationFn: async (a: { id: number; libraryItemId: number }) => {
      const { error, response } = await api.POST("/scripts/{script_id}/cast/{slot_id}/lock", { params: { path: { ...path, slot_id: a.id } }, body: { library_item_id: a.libraryItemId } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  const unlock = useMutation({
    mutationFn: async (id: number) => {
      const { error, response } = await api.DELETE("/scripts/{script_id}/cast/{slot_id}/lock", { params: { path: { ...path, slot_id: id } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  return { add, edit, remove, lock, unlock };
}

/** Claude finds the script's roles (a paid read). The price is the Claude writing rate; running is polled until it ends. */
export function useFindRoles(scriptId: number) {
  const queryClient = useQueryClient();
  const path = { script_id: scriptId };
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const status = useQuery({
    queryKey: ["script-cast-read", scriptId],
    queryFn: async () => (await api.GET("/scripts/{script_id}/cast/read", { params: { path } })).data ?? null,
    refetchInterval: (q) => (q.state.data?.running ? 2000 : false),
  });
  const running = !!status.data?.running;
  const was = useRef(running);
  useEffect(() => {
    if (was.current && !running) void queryClient.invalidateQueries({ queryKey: ["script-cast", scriptId] });
    was.current = running;
  }, [running]); // eslint-disable-line react-hooks/exhaustive-deps
  const start = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/cast/read", { params: { path } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["script-cast-read", scriptId] }),
  });
  return { price: rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit, running: running || start.isPending, problems: status.data?.problems ?? [], start };
}

export type Merged = components["schemas"]["Merged"];

/** Merge a role into another (free), see what it would move first, undo it, and answer "These may be the same person". */
export function useMergeRoles(scriptId: number) {
  const queryClient = useQueryClient();
  const path = { script_id: scriptId };
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["script-cast", scriptId] }), queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] })]);
  const preview = async (slot: number, into: number) => {
    const { data, error } = await api.GET("/scripts/{script_id}/cast/{slot_id}/merge/preview", { params: { path: { ...path, slot_id: slot }, query: { into } } });
    if (!data) throw new Error(errorText(error));
    return { ...data.moved, look_unused: data.look_unused };
  };
  const merge = async (slot: number, into: number) => {
    const { data, error } = await api.POST("/scripts/{script_id}/cast/{slot_id}/merge", { params: { path: { ...path, slot_id: slot } }, body: { into_slot_id: into } });
    if (!data) throw new Error(errorText(error));
    await refresh();
    return { moved: { ...data.moved, look_unused: data.look_unused }, token: data.token };
  };
  const undoMerge = async (token: number) => {
    const { error, response } = await api.POST("/scripts/{script_id}/cast/merge/undo", { params: { path }, body: { token } });
    if (!response.ok) throw new Error(errorText(error));
    await refresh();
  };
  const dismiss = async (a: number, b: number) => {
    const { error, response } = await api.POST("/scripts/{script_id}/cast/maybe-same/dismiss", { params: { path }, body: { a_slot_id: a, b_slot_id: b } });
    if (!response.ok) throw new Error(errorText(error));
    await refresh();
  };
  const undoDismiss = async (a: number, b: number) => {
    const { error, response } = await api.DELETE("/scripts/{script_id}/cast/maybe-same/dismiss", { params: { path }, body: { a_slot_id: a, b_slot_id: b } });
    if (!response.ok) throw new Error(errorText(error));
    await refresh();
  };
  return { preview, merge, undoMerge, dismiss, undoDismiss };
}

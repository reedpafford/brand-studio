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
  });
}

export function useCastActions(scriptId: number) {
  const queryClient = useQueryClient();
  const path = { script_id: scriptId };
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["script-cast", scriptId] }), queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] })]);
  const add = useMutation({
    mutationFn: async (a: { role: string; description: string }) => {
      const { data, error } = await api.POST("/scripts/{script_id}/cast", { params: { path }, body: a });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: refresh,
  });
  const edit = useMutation({
    mutationFn: async (a: { id: number; role?: string; description?: string }) => {
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

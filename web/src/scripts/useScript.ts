import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";

export type Script = components["schemas"]["app__routes__script_library__ScriptOut"];
export type ScriptPatch = components["schemas"]["ScriptPatch"];

/** One script with its versions' words, from the library API. */
export function useScript(id: number) {
  return useQuery({
    queryKey: ["script-lib", id],
    queryFn: async () => {
      const { data, response } = await api.GET("/scripts/{script_id}", { params: { path: { script_id: id } } });
      if (response.status === 404) return null;
      if (!data) throw new Error("load");
      return data;
    },
  });
}

/** Change the description fields (title, what it's for, reference, notes) until the script is published. */
export function usePatchScript(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ScriptPatch) => {
      const { data, error } = await api.PATCH("/scripts/{script_id}", { params: { path: { script_id: id } }, body });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["script-lib", id], data);
      return queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });
}

/** Write the original's words (slot 0) while the script is a draft. */
export function useWriteWords(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) => {
      const { data, error } = await api.PUT("/scripts/{script_id}/drafts/{slot}", { params: { path: { script_id: id, slot: 0 } }, body: { text } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["script-lib", id], data);
      return queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });
}

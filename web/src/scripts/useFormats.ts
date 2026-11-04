import { useQuery } from "@tanstack/react-query";
import { api, must } from "../api/client";
import type { components } from "../api/schema";

export type Format = components["schemas"]["FormatOut"];

/** The formats the guides offer (GET /formats), in Reed's order: a format folder added there is a new choice here. */
export const useFormats = () =>
  useQuery({
    queryKey: ["formats"],
    queryFn: async () => (await must(api.GET("/formats"))).data ?? [],
    staleTime: 300_000,
  });

/** A format's name from its id: the id itself until the formats load, or if its folder has gone. */
export function useFormatName() {
  const formats = useFormats().data;
  return (id: string) => formats?.find((f) => f.id === id)?.name ?? id;
}

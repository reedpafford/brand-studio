import { useQuery } from "@tanstack/react-query";
import { api, must } from "../api/client";

/** The server's languages (flows VS1), English first, each with whether editors may pick it. */
export function useLanguages() {
  return useQuery({ queryKey: ["languages"], queryFn: async () => (await must(api.GET("/languages"))).data! });
}

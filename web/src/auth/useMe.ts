import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

/** The signed-in user, or null when signed out. */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, response } = await api.GET("/auth/me");
      if (response.status === 401) return null;
      if (!data) throw new Error("Could not check sign-in");
      return data;
    },
    retry: false,
    staleTime: Infinity,
  });
}

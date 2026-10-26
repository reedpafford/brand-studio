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
    // A hiccup is retried quietly (about two seconds) before anyone sees "Can't reach the server".
    retry: 3,
    retryDelay: (n) => 300 * 2 ** n,
    staleTime: Infinity,
  });
}

import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useMe } from "../auth/useMe";
import { weekStop } from "../scripts/useScript";

/** An editor is never asked to send a spend to Reed: past a limit the paid button is disabled with the reason.
 *  On their own script the weekly allowance decides; on anyone else's, the video's budget does. Reed is never stopped (pressing past a budget is his approval).
 *  Returns why a price is declined, or null. */
export function useOwnScriptStop(ownScript: boolean | undefined, video?: { used: number; budget: number }) {
  const { data: me } = useMe();
  const on = !!ownScript && me?.role !== undefined && me.role !== "owner";
  const allowance = useQuery({ enabled: on, queryKey: ["allowance"], queryFn: async () => (await api.GET("/credits/me")).data ?? null });
  const editor = me?.role === "editor";
  return (cost: number | undefined): string | null => {
    if (cost === undefined) return null;
    if (on) return allowance.data ? weekStop(allowance.data, cost) : null;
    return editor && !ownScript && video && video.used + cost > video.budget ? "That's more than this video's budget." : null;
  };
}

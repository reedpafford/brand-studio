import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button } from "../components";
import { errorText as errorClass } from "../ui";
import { Dot, Tag } from "./OtherTakes";
import { clock } from "../scripts/TakePlayer";

type Piece = components["schemas"]["HostPieceOut"];

const said = (p: Piece) =>
  p.state === "making" ? "Being made…" : p.state === "ready" ? (p.number === 0 ? "On green" : `${clock(p.start)}–${clock(p.end)}`) : p.state === "failed" ? `Didn't finish: ${p.error || "try again"}` : "Not made";

/** A presenter video's host (v5's take tiles, cosmetic only): the still on green, then each piece that says the narration,
 *  each with Make again at its price. Nothing shows for a video whose format has no host. */
export function HostPieces({ projectId, aspect }: { projectId: number; aspect: string }) {
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const key = ["project-host", projectId];
  const host = useQuery({
    queryKey: key,
    queryFn: async () => (await api.GET("/projects/{project_id}/host", { params: { path } })).data,
    refetchInterval: (q) => (q.state.data?.state === "making" ? 3000 : false),
  });
  const make = useMutation({
    mutationFn: async (number: number | null) => {
      const { response, error } = number === null ? await api.POST("/projects/{project_id}/host", { params: { path } }) : await api.POST("/projects/{project_id}/host/{number}", { params: { path: { ...path, number } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const h = host.data;
  if (!h?.on) return null;
  const busy = h.state === "making" || make.isPending;
  return (
    <section aria-label="Host" className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Host</h3>
        {h.state !== "ready" && (
          <Button variant="secondary" dense busy={busy} price={h.credits} charge="fixed" onClick={() => make.mutate(null)}>
            Make the host
          </Button>
        )}
      </div>
      {make.error && <p role="alert" className={errorClass}>{make.error.message}</p>}
      <ul className="grid grid-cols-3 gap-2" aria-label="Host pieces">
        {h.pieces.map((p) => (
          <li key={p.number} className="space-y-1" aria-label={p.number === 0 ? "Host still" : `Host piece ${p.number}`}>
            <div className="relative overflow-hidden rounded-md bg-surface-2" style={{ aspectRatio: aspect.replace(":", " / ") }}>
              {p.file_id != null && (p.number === 0 ? <img src={fileUrl(p.file_id)} alt="The host on green" className="h-full w-full object-cover" /> : <video controls playsInline preload="metadata" src={fileUrl(p.file_id)} className="h-full w-full object-cover" aria-label={`Host piece ${p.number}`} />)}
              <Tag>{p.number === 0 ? "Still" : `Piece ${p.number}`}</Tag>
            </div>
            <Dot tone={p.state === "ready" ? "ok" : p.state === "failed" ? "need" : p.state === "making" ? "run" : "none"}>{said(p)}</Dot>
            {p.state !== "making" && p.state !== "none" && (
              <Button variant="ghost" dense disabled={busy} price={p.credits} charge="fixed" onClick={() => make.mutate(p.number)}>
                Make again
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

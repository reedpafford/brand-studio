import { useQuery } from "@tanstack/react-query";
import { Wand2 } from "lucide-react";
import { api } from "../api/client";
import { Banner, Button } from "../components";

/** What rewriting costs: every stale clip, or one clip. Nothing is asked until a clip is stale. */
export function useRewritePrice(projectId: number, clipId?: string) {
  const price = useQuery({
    queryKey: ["rewrite-price", projectId, clipId ?? "all"],
    queryFn: async () => (await api.GET("/projects/{project_id}/clips/prompts/price", { params: { path: { project_id: projectId }, query: clipId ? { clip_id: clipId } : {} } })).data ?? null,
  });
  return price.data?.credits;
}

type Props = { projectId: number; busy: boolean; stopFor: (cost: number | undefined) => string | null; onRewrite: () => void };

/** The Clips step never dead-ends: clips written for an older breakdown get their prompts written again (takes are kept). */
/** `inBar`: the rewrite is the cost bar's press (the video page), so the banner only says what happened. */
export function RewriteNote({ count, inBar, ...props }: Props & { count: number; writing: boolean; inBar?: boolean }) {
  const price = useRewritePrice(props.projectId);
  if (props.writing) return <Banner tone="info" title="Rewriting clip prompts…" />;
  const stop = props.stopFor(price);
  return (
    <Banner
      tone="warning"
      title={`${count} clip${count === 1 ? " was" : "s were"} made for an older breakdown. Rewrite ${count === 1 ? "its prompt" : "their prompts"} so ${count === 1 ? "it matches" : "they match"}.`}
      action={
        inBar ? undefined : (
          <Button busy={props.busy} price={price} reason={stop} disabled={!!stop} onClick={props.onRewrite}>
            Rewrite clip prompts
          </Button>
        )
      }
    />
  );
}

/** In place of "Change this…" on a stale clip. */
export function RewriteOne({ clipId, ...props }: Props & { clipId: string }) {
  const price = useRewritePrice(props.projectId, clipId);
  const stop = props.stopFor(price);
  return (
    <Button variant="secondary" icon={Wand2} busy={props.busy} price={price} reason={stop} disabled={!!stop} onClick={props.onRewrite}>
      Rewrite this clip&apos;s prompt
    </Button>
  );
}

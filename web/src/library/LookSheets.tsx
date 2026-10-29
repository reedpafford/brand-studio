import { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Button } from "../components";
import { useLooks } from "../scripts/Looks";
import { useToast } from "../toast";
import { card, errorText as errorClass } from "../ui";
import { useSheetPrice } from "./SheetPanel";

type Item = components["schemas"]["ItemOut"];

/** A character's sheet in each look besides House (flows ST2; Next-Server's #930). Only the owner adds one; a video in a
 *  look without one makes its own copy at Assets instead. */
export function LookSheets({ item }: { item: Item }) {
  const owner = useMe().data?.role === "owner";
  const looks = (useLooks().data ?? []).filter((l) => l.id !== "house");
  const queryClient = useQueryClient();
  const toast = useToast();
  const { model, price } = useSheetPrice();
  const sheets = item.look_sheets ?? {};
  const path = { kind: "character" as const, item_id: item.id };
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", "character"] });
  const drawing = Object.values(sheets).some((s) => s.status === "drawing");
  // While one is drawn, read the character again until its sheet is in.
  useEffect(() => {
    if (!drawing) return;
    const t = setInterval(() => void refresh(), 3000);
    return () => clearInterval(t);
  }, [drawing]); // eslint-disable-line react-hooks/exhaustive-deps
  const make = useMutation({
    mutationFn: (look_id: string) => must(api.POST("/library/{kind}/{item_id}/sheet", { params: { path }, body: { model_id: model, change: "", look_id } })),
    onSuccess: refresh,
  });
  const approve = useMutation({
    mutationFn: (look_id: string) => must(api.POST("/library/{kind}/{item_id}/sheet/approve", { params: { path, query: { look_id } } })),
    onSuccess: async (_r, look_id) => {
      await refresh();
      toast("Sheet approved.", async () => {
        await api.DELETE("/library/{kind}/{item_id}/sheet/approve", { params: { path, query: { look_id } } });
        await refresh();
      });
    },
  });
  if (looks.length === 0) return null;
  const refused = (make.error ?? approve.error)?.message;
  return (
    <section aria-label="Sheets in other looks" className={`${card} space-y-3`}>
      <div>
        <h2 className="font-medium">Sheets in other looks</h2>
        <p className="text-sm text-muted">The House sheet is above. A video in a look with no sheet here makes its own look for that video.</p>
      </div>
      {refused && <p role="alert" className={errorClass}>{refused}</p>}
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {looks.map((l) => {
          const s = sheets[l.id] ?? { file_id: null, status: "none" as const };
          return (
            <li key={l.id} className="space-y-2 text-sm" aria-label={`${l.name} sheet`}>
              <div className="grid aspect-[9/16] place-items-center overflow-hidden rounded-md bg-surface-2">
                {s.file_id ? <img src={fileUrl(s.file_id)} alt={`${item.name} in ${l.name}`} className="h-full w-full object-cover" /> : <span className={`text-muted ${s.status === "drawing" ? "animate-pulse" : ""}`}>{s.status === "drawing" ? "Drawing…" : "No sheet yet"}</span>}
              </div>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {l.name}
                {s.status === "approved" && <Badge tone="success">Approved</Badge>}
                {s.status === "waiting_for_owner" && <Badge>Waiting for the owner</Badge>}
              </p>
              {owner && s.status === "none" && (
                <Button variant="secondary" dense price={price} busy={make.isPending && make.variables === l.id} onClick={() => make.mutate(l.id)}>
                  Make a {l.name} sheet
                </Button>
              )}
              {owner && s.status === "needs_approval" && (
                <div className="flex flex-wrap gap-2">
                  <Button dense busy={approve.isPending && approve.variables === l.id} onClick={() => approve.mutate(l.id)}>Approve</Button>
                  <Button variant="ghost" dense price={price} busy={make.isPending && make.variables === l.id} onClick={() => make.mutate(l.id)}>Redo</Button>
                </div>
              )}
              {!owner && s.status === "none" && <p className="text-muted">Only the owner adds a sheet in a look.</p>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Star, Trash2, X } from "lucide-react";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Link } from "react-router-dom";
import { Badge, Button, Card, Field, Select, buttonClass } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

/** Brand setup (flows BR1; Builder-Server-7's #910): the brand's voice, CTA lines and defaults. */
export type CtaLine = components["schemas"]["CtaLine"];
export type CastPick = components["schemas"]["CastPick"];
type Brand = components["schemas"]["BrandOut"];

/** The server has brand setup when the brand carries its CTA lines (#910); without them the page stays as it was. */
export const setupOf = (b: Brand) => ("cta_lines" in b ? (b as Required<Brand>) : null);

/** CTA lines: several, one marked Default; each change saves at once, and every delete has Undo (BR1). Editors change them too (Reed, 30 Oct). */
export function CtaLines({ brandId, lines, advice }: { brandId: number; lines: CtaLine[]; advice: string[] }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [text, setText] = useState("");
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const path = { brand_id: brandId };
  const line = (line_id: string) => ({ params: { path: { ...path, line_id } } });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["brands"] });
  const add = useMutation({ mutationFn: () => must(api.POST("/brands/{brand_id}/cta-lines", { params: { path }, body: { text: text.trim(), default: false } })), onSuccess: () => { setText(""); return refresh(); } });
  const edit = useMutation({ mutationFn: (v: { id: string; text?: string; default?: boolean }) => must(api.PATCH("/brands/{brand_id}/cta-lines/{line_id}", { ...line(v.id), body: { text: v.text, default: v.default } })), onSuccess: () => { setEditing(null); return refresh(); } });
  const remove = useMutation({
    mutationFn: async (l: CtaLine) => (await must(api.DELETE("/brands/{brand_id}/cta-lines/{line_id}", line(l.id)))).data!,
    onSuccess: async (r, l) => {
      await refresh();
      const next = lines.find((x) => x.id === r.promoted_id);
      const undo = () => void must(api.POST("/brands/{brand_id}/cta-lines/{line_id}/restore", line(l.id))).then(refresh, (e: Error) => toast(e.message, undefined, "error"));
      toast(next ? `Deleted. "${next.text}" is now the Default.` : "Deleted.", undo);
    },
  });
  const latest = [add, edit, remove].reduce((a, m) => (m.submittedAt > a.submittedAt ? m : a));
  return (
    <Card className="min-w-0 space-y-3">
      <div>
        <h2 className="type-section">Call to action</h2>
        <p className="text-sm text-muted">The last clip of a video says the Default line.</p>
      </div>
      {advice.map((a) => (
        <p key={a} className="text-sm text-warning">{a}</p>
      ))}
      {latest.isError && <p role="alert" className={errorClass}>{latest.error.message}</p>}
      <ul className="space-y-2" aria-label="Call to action lines">
        {lines.map((l) =>
          editing?.id === l.id ? (
            <li key={l.id} className="space-y-2">
              <Field label="Line" value={editing.text} maxLength={500} onChange={(e) => setEditing({ ...editing, text: e.target.value })} />
              <div className="flex gap-2">
                <Button variant="secondary" dense busy={edit.isPending} disabled={!editing.text.trim()} reason={!editing.text.trim() ? "Write the line first" : null} onClick={() => edit.mutate({ id: l.id, text: editing.text.trim() })}>Save line</Button>
                <Button variant="ghost" dense onClick={() => setEditing(null)}>Cancel</Button>
              </div>
            </li>
          ) : (
            <li key={l.id} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="min-w-0 flex-1 break-words">{l.text}</span>
              {l.default ? <Badge tone="success" icon={Star}>Default</Badge> : <Button variant="ghost" dense busy={edit.isPending && edit.variables?.id === l.id} onClick={() => edit.mutate({ id: l.id, default: true })}>Make default</Button>}
              <Button variant="ghost" dense aria-label={`Edit "${l.text}"`} onClick={() => setEditing({ id: l.id, text: l.text })}>Edit</Button>
              <Button variant="ghost" dense icon={Trash2} aria-label={`Delete "${l.text}"`} busy={remove.isPending && remove.variables?.id === l.id} onClick={() => remove.mutate(l)} />
            </li>
          ),
        )}
      </ul>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1">
          <Field label="Add a line" value={text} maxLength={500} placeholder="Find us through the link in my bio." onChange={(e) => setText(e.target.value)} />
        </div>
        <Button variant="secondary" icon={Plus} busy={add.isPending} disabled={!text.trim()} reason={!text.trim() ? "Write the line first" : null} onClick={() => add.mutate()}>Add line</Button>
      </div>
    </Card>
  );
}

/** Default cast: library characters a new script starts with. One deleted since reads "Deleted: pick another" (BR1). */
export function DefaultCast({ brandId, value, picks, onChange }: { brandId: number; value: number[]; picks: CastPick[]; onChange: (ids: number[]) => void }) {
  const [replacing, setReplacing] = useState<number | null>(null);
  const library = useQuery({
    queryKey: ["library", "character", brandId, false],
    queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind: "character" }, query: { brand_id: brandId } } })).data ?? [],
  });
  // Only workspace characters, never a look made for one video or script.
  const workspace = (library.data ?? []).filter((c) => !c.owner_project_id && !c.owner_script_id);
  const choices = workspace.filter((c) => !value.includes(c.id));
  const nameOf = (id: number) => library.data?.find((c) => c.id === id)?.name ?? picks.find((p) => p.id === id)?.name ?? "A character";
  const gone = (id: number) => picks.find((p) => p.id === id)?.deleted ?? false;
  const picker = (label: string, onPick: (id: number) => void) => (
    <Select label={label} value="" disabled={choices.length === 0} hint={library.data && choices.length === 0 ? "Every character in Cast & places is picked." : undefined} onChange={(e) => e.target.value && onPick(Number(e.target.value))}>
      <option value="">Pick a character…</option>
      {choices.map((c) => (
        <option key={c.id} value={c.id}>{c.name}</option>
      ))}
    </Select>
  );
  return (
    <fieldset className="min-w-0 space-y-2">
      <legend className="text-sm font-medium">Default cast</legend>
      {value.length === 0 && <p className="text-sm text-muted">New scripts start with nobody picked.</p>}
      <ul className="space-y-2">
        {value.map((id) => (
          <li key={id} className="space-y-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1">{gone(id) ? <span className="text-warning">Deleted: pick another</span> : nameOf(id)}</span>
              {gone(id) && <Button variant="secondary" dense onClick={() => setReplacing(replacing === id ? null : id)} aria-expanded={replacing === id}>Pick another</Button>}
              <Button variant="ghost" dense icon={X} aria-label={`Remove ${gone(id) ? "the deleted character" : nameOf(id)}`} onClick={() => onChange(value.filter((x) => x !== id))}>{gone(id) ? "Remove" : ""}</Button>
            </div>
            {replacing === id && picker("Instead", (pick) => { onChange(value.map((x) => (x === id ? pick : x))); setReplacing(null); })}
          </li>
        ))}
      </ul>
      {library.data && workspace.length === 0 ? (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">No characters yet.</span>
          <Link className={buttonClass("secondary")} to={`/b/${brandId}/library`}>Add one in Cast & places</Link>
        </p>
      ) : (
        picker("Add to the default cast", (pick) => onChange([...value, pick]))
      )}
    </fieldset>
  );
}

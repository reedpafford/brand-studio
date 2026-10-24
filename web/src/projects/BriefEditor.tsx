import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { btnPrimary, btnSecondary, errorText as errorClass, input, linkText } from "../ui";
import { CastPicker, FlavourPicker, ReferencePicker, useBriefChoices, useLongestSeconds, useReferences } from "./BriefPickers";

type Project = components["schemas"]["ProjectOut"];

/** The brief as it stands, with Edit: cast, flavour, length and the words can change after the project is made. */
export function BriefEditor({ project, hasScript, onNext }: { project: Project; hasScript: boolean; onNext: () => void }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [goal, setGoal] = useState(project.goal);
  const [format, setFormat] = useState(project.format);
  const [seconds, setSeconds] = useState(project.planned_seconds);
  const [cast, setCast] = useState(project.cast_ids);
  const picked = (project.reference_breakdown as { source_id?: string } | null)?.source_id ?? null;
  const [reel, setReel] = useState<{ id: string | null; replace: string }>({ id: picked, replace: project.reference_replace ?? "" });
  const refs = useReferences();
  const [picks, setPicks] = useState<Record<string, string>>(project.product_variants ?? {});
  const { characters, products, chosen, unchosen } = useBriefChoices(project.brand_id, picks);
  const longest = useLongestSeconds();
  const save = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.PATCH("/projects/{project_id}", {
        params: { path: { project_id: project.id } },
        body: {
          goal,
          format,
          planned_seconds: seconds,
          cast_ids: cast,
          product_variants: Object.fromEntries([...products.keys()].map((p) => [p, chosen(p)!])),
          // Picking a reel sets it (with what to replace); clearing it removes it.
          ...(reel.id ? { reference_id: reel.id, reference_replace: reel.replace } : picked ? { reference_breakdown: null, reference_replace: "" } : {}),
        },
      });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["project", project.id] }), queryClient.invalidateQueries({ queryKey: ["project-estimate", project.id] }), queryClient.invalidateQueries({ queryKey: ["projects"] })]);
      setEditing(false);
    },
  });
  // Each time Edit brief opens, the fields start from what is saved (a Cancel earlier doesn't linger).
  const startEditing = () => {
    setGoal(project.goal);
    setFormat(project.format);
    setSeconds(project.planned_seconds);
    setCast(project.cast_ids);
    setPicks(project.product_variants ?? {});
    setReel({ id: picked, replace: project.reference_replace ?? "" });
    setEditing(true);
  };
  const names = characters.data?.filter((c) => project.cast_ids.includes(c.id)).map((c) => c.name) ?? [];
  const flavours = Object.entries(project.product_variants ?? {});

  if (!editing)
    return (
      <div className="space-y-2">
        {project.goal ? <p>{project.goal}</p> : <p className="text-muted">What's this video for? A few lines is enough. Claude turns it into a script.</p>}
        <p className="text-muted">{[project.platform, project.aspect_ratio, project.format, `${project.planned_seconds}s planned`].filter(Boolean).join(" · ")}</p>
        {names.length > 0 && <p>In it: {names.join(", ")}</p>}
        {picked && (
          <p>
            Adapting: {refs.data?.find((r) => r.id === picked)?.name ?? picked}
            {project.reference_replace && <span className="block text-muted">Replace: {project.reference_replace}</span>}
          </p>
        )}
        {flavours.map(([product, variant]) => (
          <p key={product}>
            {product.charAt(0).toUpperCase() + product.slice(1)}: {variant}
          </p>
        ))}
        <div className="flex flex-wrap items-center gap-3">
          <button className={`${btnPrimary} min-h-11 sm:min-h-9`} onClick={onNext}>
            Next: Script →
          </button>
          <button className={`${linkText} min-h-11 sm:min-h-0`} onClick={startEditing}>
            Edit brief
          </button>
        </div>
      </div>
    );

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <label className="block">
        What's it for?
        <textarea className={input} rows={4} value={goal} onChange={(e) => setGoal(e.target.value)} />
      </label>
      <label className="block">
        Kind of video (optional)
        <input className={input} value={format} onChange={(e) => setFormat(e.target.value)} />
      </label>
      <label className="block">
        Planned length (seconds)
        <input className={input} type="number" required min={1} max={longest} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} />
        <span className="block text-muted">Budget: {seconds * 2} credits (twice the length).</span>
      </label>
      <CastPicker characters={characters.data} cast={cast} onChange={setCast} />
      <FlavourPicker products={products} chosen={chosen} onPick={(product, variant) => setPicks({ ...picks, [product]: variant })} />
      <ReferencePicker value={reel.id} replace={reel.replace} onChange={(id, replace) => setReel({ id, replace })} />
      {hasScript && <p className="text-sm text-muted">Saving doesn't rewrite the script or the steps after it. Redo them if the change matters.</p>}
      {save.isError && <p role="alert" className={errorClass}>{save.error.message}</p>}
      <div className="flex gap-2">
        <button className={`${btnPrimary} min-h-11 sm:min-h-9`} disabled={save.isPending || !!unchosen}>
          Save brief
        </button>
        <button type="button" className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={() => setEditing(false)}>
          Cancel
        </button>
      </div>
      {unchosen && <p className="text-muted">Pick which {unchosen} first.</p>}
    </form>
  );
}

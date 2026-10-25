import { useState, type FormEvent } from "react";
import { Banner, Button, Field, TextArea } from "../components";
import { ReferenceList } from "./ReferenceList";

export type Description = { title: string; description: string; notes: string; reference_id: string | null; reference_replace: string };
export const emptyDescription: Description = { title: "", description: "", notes: "", reference_id: null, reference_replace: "" };

/** The fields of step 1, used both to make a script and to edit its description. */
export function DescriptionForm({ initial = emptyDescription, brandName, submitLabel, busy, error, onSubmit, onCancel }: { initial?: Description; brandName?: string; submitLabel: string; busy: boolean; error?: string | null; onSubmit: (d: Description) => void; onCancel?: () => void }) {
  const [d, setD] = useState(initial);
  const reason = !d.title.trim() ? "Add a title first" : !d.description.trim() ? "Say what it's for first" : null;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!reason) onSubmit({ ...d, title: d.title.trim(), description: d.description.trim() });
  };
  return (
    <form onSubmit={submit} className="max-w-[680px] space-y-5">
      <Field label="Title" placeholder="e.g. Bo tries salmon" value={d.title} onChange={(e) => setD({ ...d, title: e.target.value })} />
      <TextArea label="What it's for" rows={4} maxLength={2000} counter={`${d.description.length} / 2,000`} hint="A few lines is enough. Claude writes the script from this." value={d.description} onChange={(e) => setD({ ...d, description: e.target.value })} />
      <ReferenceList value={d.reference_id} replace={d.reference_replace} onChange={(id, replace) => setD({ ...d, reference_id: id, reference_replace: replace })} />
      <TextArea label="Notes (optional)" rows={3} hint="Anything Claude should know: tone, a line to keep, what to avoid." value={d.notes} onChange={(e) => setD({ ...d, notes: e.target.value })} />
      {brandName && <p className="text-sm text-muted">For {brandName}</p>}
      {error && <Banner title={error} />}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" busy={busy} disabled={reason !== null} reason={reason}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

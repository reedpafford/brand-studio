import { useMutation } from "@tanstack/react-query";
import { fileUrl, uploadFile } from "../api/upload";
import { btnSecondary, errorText as errorClass, input, linkText } from "../ui";

export type Outfit = { name: string; file_ids: number[] };

/** Character-only fields: outfits (named sets of pictures) and a voice sample. */
export function CharacterExtras(props: {
  outfits: Outfit[];
  voiceFileId: number | null;
  onOutfits: (o: Outfit[]) => void;
  onVoice: (id: number | null) => void;
}) {
  const { outfits, onOutfits } = props;
  const patch = (i: number, o: Outfit) => onOutfits(outfits.map((x, j) => (j === i ? o : x)));
  const addPicture = useMutation({ mutationFn: ({ file }: { file: File; i: number }) => uploadFile(file), onSuccess: (f, { i }) => patch(i, { ...outfits[i], file_ids: [...outfits[i].file_ids, f.id] }) });
  const addVoice = useMutation({ mutationFn: uploadFile, onSuccess: (f) => props.onVoice(f.id) });

  return (
    <>
      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">Outfits</legend>
        {outfits.map((o, i) => (
          <div key={i} className="space-y-2 rounded-md border border-border p-3">
            <div className="flex gap-2">
              <input className={input} aria-label={`Outfit ${i + 1} name`} required value={o.name} onChange={(e) => patch(i, { ...o, name: e.target.value })} />
              <button type="button" className={linkText} aria-label={`Remove outfit ${i + 1}`} onClick={() => onOutfits(outfits.filter((_, j) => j !== i))}>
                Remove
              </button>
            </div>
            <ul className="flex flex-wrap gap-2">
              {o.file_ids.map((id) => (
                <li key={id} className="space-y-1 text-sm">
                  <img src={fileUrl(id)} alt={o.name} className="size-16 rounded-sm border border-border object-cover" />
                  <button type="button" className={linkText} aria-label={`Remove picture from ${o.name}`} onClick={() => patch(i, { ...o, file_ids: o.file_ids.filter((x) => x !== id) })}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <label className={`inline-block cursor-pointer text-sm ${linkText}`}>
              Add picture
              <input type="file" accept="image/*" className="sr-only" aria-label={`Add picture to outfit ${i + 1}`} onChange={(e) => e.target.files?.[0] && addPicture.mutate({ file: e.target.files[0], i })} />
            </label>
          </div>
        ))}
        <button type="button" className={btnSecondary} onClick={() => onOutfits([...outfits, { name: "", file_ids: [] }])}>
          Add outfit
        </button>
        {addPicture.isError && <p role="alert" className={errorClass}>{addPicture.error.message}</p>}
      </fieldset>
      <div className="space-y-1 text-sm">
        <div className="font-medium">Voice sample</div>
        {props.voiceFileId && <audio controls src={fileUrl(props.voiceFileId)} aria-label="Voice sample" className="w-full" />}
        <div className="flex gap-3">
          <label className={`inline-flex min-h-11 cursor-pointer items-center sm:min-h-0 ${linkText}`}>
            {props.voiceFileId ? "Replace voice" : "Add voice"}
            <input type="file" accept="audio/*" className="sr-only" aria-label="Voice file" onChange={(e) => e.target.files?.[0] && addVoice.mutate(e.target.files[0])} />
          </label>
          {props.voiceFileId && (
            <button type="button" className={linkText} onClick={() => props.onVoice(null)}>
              Remove voice
            </button>
          )}
        </div>
        {addVoice.isError && <p role="alert" className={errorClass}>{addVoice.error.message}</p>}
      </div>
    </>
  );
}

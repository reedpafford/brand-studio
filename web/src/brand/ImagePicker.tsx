import { useMutation } from "@tanstack/react-query";
import { fileUrl, uploadFile } from "../api/upload";
import { errorText, linkText } from "../ui";

/** A labelled image slot: shows the current image, picks and uploads a new one. */
export function ImagePicker(props: { label: string; fileId: number | null; onChange: (id: number | null) => void }) {
  const upload = useMutation({
    mutationFn: uploadFile,
    onSuccess: (f) => props.onChange(f.id),
  });
  return (
    <div className="space-y-1 text-sm">
      <div className="font-medium">{props.label}</div>
      {props.fileId && <img src={fileUrl(props.fileId)} alt={props.label} className="h-24 rounded border border-border bg-surface-2 object-contain" />}
      <div className="flex items-center gap-3">
        <label className={`cursor-pointer ${linkText}`}>
          {props.fileId ? "Replace" : "Upload"}
          <input
            type="file"
            accept="image/*"
            className="sr-only"
            aria-label={`${props.label} file`}
            onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])}
          />
        </label>
        {props.fileId && (
          <button type="button" className={linkText} onClick={() => props.onChange(null)}>
            Remove
          </button>
        )}
        {upload.isPending && <span className="text-muted">Uploading…</span>}
      </div>
      {upload.isError && (
        <p role="alert" className={errorText}>
          {upload.error.message}
        </p>
      )}
    </div>
  );
}

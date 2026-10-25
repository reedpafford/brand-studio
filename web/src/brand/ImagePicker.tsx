import { useMutation } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { fileUrl, uploadFile } from "../api/upload";
import { Button, buttonClass } from "../components";
import { errorText } from "../ui";

/** A labelled image slot: a tile with the current image, and Replace (or Upload) to pick a new one. */
export function ImagePicker(props: { label: string; fileId: number | null; onChange: (id: number | null) => void; shape?: "square" | "wide" | "tall" }) {
  const upload = useMutation({
    mutationFn: uploadFile,
    onSuccess: (f) => props.onChange(f.id),
  });
  const aspect = props.shape === "wide" ? "16 / 9" : props.shape === "tall" ? "9 / 16" : "1 / 1";
  return (
    <div className="space-y-2">
      <div className="text-sm font-medium">{props.label}</div>
      <div className="grid w-24 place-items-center overflow-hidden rounded-lg border border-border bg-surface-2 text-muted" style={{ aspectRatio: aspect, width: props.shape === "wide" ? "9rem" : undefined }}>
        {props.fileId ? <img src={fileUrl(props.fileId)} alt={props.label} className="size-full object-contain" /> : <Upload size={20} strokeWidth={1.75} aria-hidden />}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className={`${buttonClass("secondary")} cursor-pointer text-sm focus-within:outline focus-within:outline-2 focus-within:outline-accent lg:min-h-control-dense lg:px-3`}>
          {props.fileId ? "Replace" : "Upload"}
          <input type="file" accept="image/*" className="sr-only" aria-label={`${props.label} file`} onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
        </label>
        {props.fileId && (
          <Button type="button" variant="ghost" dense onClick={() => props.onChange(null)}>
            Remove
          </Button>
        )}
        {upload.isPending && <span className="text-sm text-muted">Uploading…</span>}
      </div>
      {upload.isError && (
        <p role="alert" className={errorText}>
          {upload.error.message}
        </p>
      )}
    </div>
  );
}

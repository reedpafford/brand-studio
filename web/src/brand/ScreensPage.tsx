import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";

const slugs = (s: string) => s.split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);

/** The brand's real screens. Tags say what a screen shows; "moments" say when it is used automatically. */
export function ScreensPage() {
  const brand_id = Number(useParams().brandId);
  const queryClient = useQueryClient();
  const key = ["screens", brand_id];
  const screens = useQuery({
    queryKey: key,
    queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id } } })).data ?? [],
  });
  const remove = useMutation({
    mutationFn: (screen_id: number) => api.DELETE("/brands/{brand_id}/screens/{screen_id}", { params: { path: { brand_id, screen_id } } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Screens</h1>
      <AddScreen brandId={brand_id} onDone={() => queryClient.invalidateQueries({ queryKey: key })} />
      {screens.data?.length === 0 && <p className="text-neutral-600">No screens yet. Add the real app screens that must appear in videos.</p>}
      <ul className="grid grid-cols-2 gap-4 md:grid-cols-3">
        {screens.data?.map((s) => (
          <li key={s.id} className="space-y-1 text-sm">
            <img src={fileUrl(s.file_id)} alt={s.name} className="aspect-[9/16] w-full rounded border border-neutral-200 object-cover" />
            <div className="font-medium">{s.name}</div>
            {s.tags.length > 0 && <div className="text-neutral-600">Shows: {s.tags.join(", ")}</div>}
            {s.default_for.length > 0 && <div className="text-neutral-600">Used for: {s.default_for.join(", ")}</div>}
            <button
              className="underline"
              aria-label={`Delete ${s.name}`}
              onClick={() => window.confirm(`Delete the screen "${s.name}"?`) && remove.mutate(s.id)}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}

function AddScreen({ brandId, onDone }: { brandId: number; onDone: () => void }) {
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");
  const [moments, setMoments] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const add = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose an image first.");
      const stored = await uploadFile(file);
      const { data, error } = await api.POST("/brands/{brand_id}/screens", {
        params: { path: { brand_id: brandId } },
        body: { name, file_id: stored.id, tags: slugs(tags), default_for: slugs(moments) },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      setName("");
      setTags("");
      setMoments("");
      setFile(null);
      onDone();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  const box = "w-full rounded border border-neutral-300 px-3 py-2 text-base";
  return (
    <form onSubmit={submit} className="space-y-3 rounded border border-neutral-200 p-4">
      <h2 className="font-semibold">Add a screen</h2>
      <label className="block text-sm">
        Screen image
        <input
          type="file"
          accept="image/*"
          className={box}
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            setFile(f);
            if (f && !name) setName(f.name.replace(/\.[^.]+$/, ""));
          }}
        />
      </label>
      <label className="block text-sm">
        Name
        <input className={box} required value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="block text-sm">
        What it shows (tags, separated by commas)
        <input className={box} value={tags} onChange={(e) => setTags(e.target.value)} />
      </label>
      <label className="block text-sm">
        Use automatically for these moments (separated by commas)
        <input className={box} value={moments} onChange={(e) => setMoments(e.target.value)} />
      </label>
      {add.isError && (
        <p role="alert" className="text-sm text-red-700">
          {add.error.message}
        </p>
      )}
      <button className="rounded bg-neutral-900 px-4 py-2 text-white disabled:opacity-50" disabled={add.isPending}>
        Add screen
      </button>
    </form>
  );
}

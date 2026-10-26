import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Archive, Ellipsis } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Dialog, Menu, MenuItem } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

type Brand = { id: number; name: string };

/** Bring an archived brand back (Undo, and Restore on Usage). */
export function useRestoreBrand() {
  const queryClient = useQueryClient();
  const toast = useToast();
  return async (b: Brand, quiet = false) => {
    const { error, response } = await api.POST("/brands/{brand_id}/restore", { params: { path: { brand_id: b.id } } });
    if (!response.ok) return toast(errorText(error), undefined, "error");
    await Promise.all([queryClient.invalidateQueries({ queryKey: ["brands"] }), queryClient.invalidateQueries({ queryKey: ["usage"] })]);
    if (!quiet) toast(`Brought back ${b.name}.`);
  };
}

/** Archive brand, for Reed: a menu next to the page title, a confirm, then the app moves to the first other brand with an Undo. */
export function ArchiveBrand({ brand, others }: { brand: Brand; others: Brand[] }) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const restore = useRestoreBrand();
  const confirm = async () => {
    setBusy(true);
    setProblem(null);
    const { error, response } = await api.DELETE("/brands/{brand_id}", { params: { path: { brand_id: brand.id } } });
    setBusy(false);
    if (!response.ok) return setProblem(errorText(error));
    setAsking(false);
    await Promise.all([queryClient.invalidateQueries({ queryKey: ["brands"] }), queryClient.invalidateQueries({ queryKey: ["usage"] })]);
    navigate(others[0] ? `/b/${others[0].id}` : "/team", { replace: true });
    toast(`Archived ${brand.name}.`, () => void restore(brand));
  };
  return (
    <>
      <Menu
        title={`More for ${brand.name}`}
        align="right"
        trigger={(p) => (
          <button type="button" {...p} aria-label={`More for ${brand.name}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2">
            <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
          </button>
        )}
      >
        {(close) => (
          <MenuItem
            danger
            onClick={() => {
              close();
              setAsking(true);
            }}
          >
            <Archive size={20} strokeWidth={1.75} aria-hidden />
            Archive brand
          </MenuItem>
        )}
      </Menu>
      {asking && (
        <Dialog title={`Archive ${brand.name}?`} cancelLabel="Keep it" actionLabel="Archive" danger busy={busy} onCancel={() => setAsking(false)} onConfirm={() => void confirm()}>
          It leaves the brand menu. Its scripts, videos and screens are kept, and you can bring it back from Usage.
          {problem && <p role="alert" className={`mt-2 ${errorClass}`}>Couldn't do that. Nothing changed. {problem}</p>}
        </Dialog>
      )}
    </>
  );
}

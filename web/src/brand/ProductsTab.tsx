import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Ellipsis, Package, Plus } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Banner, Button, Card, EmptyState, Field, Menu, MenuItem, Skeleton } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { BrandAction } from "./BrandPage";
import { ImagePicker } from "./ImagePicker";
import { Panel, ScreenEditor, groupProducts, useAddScreen, useScreens, type Screen } from "./screens";

/** Products are the brand's screens grouped by their product field; each flavour is the screen marked for it. */
export function ProductsTab() {
  const brandId = Number(useParams().brandId);
  const screens = useScreens(brandId);
  const [editing, setEditing] = useState<Screen | null>(null);
  const [adding, setAdding] = useState<{ product?: string } | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const groups = groupProducts(screens.data ?? []);
  const addButton = <Button icon={Plus} onClick={() => setAdding({})}>Add product</Button>;
  return (
    <div className="space-y-4">
      <BrandAction>{addButton}</BrandAction>
      {/* BR1: a product's line and main claim live on its page in Cast & places (its prop), not on these screens. */}
      <p className="text-sm text-muted">
        Each product's line and main claim are on its page in Cast & places.{" "}
        <Link className="inline-flex min-h-control items-center text-accent-text hover:underline sm:min-h-0" to={`/b/${brandId}/library/props`}>Open Cast & places</Link>
      </p>
      {screens.isError && <Banner title="Couldn't load the products." action={<Button variant="secondary" onClick={() => void screens.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {screens.isPending && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="aspect-square rounded-lg" />
          ))}
        </div>
      )}
      {screens.data && groups.length === 0 && (
        <EmptyState icon={Package} title="No products yet." action={addButton}>
          Add a product and its flavours so briefs can pick them.
        </EmptyState>
      )}
      {groups.map(({ name: product, screens: list }) => (
        // v5 F_BrandProducts: a 960 px card per product; its name with the count small and muted, Add flavour and ⋯ on the
        // right, then each flavour as a 120 px square with its name under it.
        <Card key={product.toLowerCase()} className="max-w-[960px] space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-baseline gap-2 text-md font-semibold">
              {product} <span className="text-xs font-normal text-muted">{list.length} flavour{list.length === 1 ? "" : "s"}</span>
            </h2>
            <span className="ml-auto flex items-center gap-1">
              <Button variant="secondary" dense icon={Plus} aria-label={`Add a flavour to ${product}`} onClick={() => setAdding({ product })}>
                Add flavour
              </Button>
            <Menu title={product} align="right" trigger={(t) => <button type="button" {...t} aria-label={`More for ${product}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2"><Ellipsis size={20} strokeWidth={1.75} aria-hidden /></button>}>
              {(close) => (
                <MenuItem
                  onClick={() => {
                    close();
                    setRenaming(product);
                  }}
                >
                  Rename {product}
                </MenuItem>
              )}
            </Menu>
            </span>
          </div>
          <ul className="flex flex-wrap gap-3">
            {list.map((s) => (
              <li key={s.id} className="w-30">
                <button type="button" onClick={() => setEditing(s)} className="block w-full space-y-1.5 text-left">
                  <span className="grid aspect-square w-full place-items-center overflow-hidden rounded-lg bg-surface-2 text-muted hover:opacity-90">
                    {s.file_id ? <img src={fileUrl(s.file_id)} alt="" className="size-full object-cover" /> : <Package size={24} strokeWidth={1.75} aria-hidden />}
                  </span>
                  <span className="block truncate text-sm">{s.variant || s.name}</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      ))}
      {editing && <ScreenEditor key={editing.id} brandId={brandId} screen={editing} onClose={() => setEditing(null)} />}
      {adding && <AddProduct brandId={brandId} product={adding.product} onClose={() => setAdding(null)} />}
      {renaming && <RenameProduct brandId={brandId} product={renaming} screens={groups.find((g) => g.name === renaming)?.screens ?? []} onClose={() => setRenaming(null)} />}
    </div>
  );
}

/** A new product (name, first flavour's picture and name), or one more flavour for a product that is there. */
function AddProduct({ brandId, product, onClose }: { brandId: number; product?: string; onClose: () => void }) {
  const toast = useToast();
  const add = useAddScreen(brandId);
  const [name, setName] = useState(product ?? "");
  const [flavour, setFlavour] = useState("");
  const [fileId, setFileId] = useState<number | null>(null);
  const ready = fileId !== null && name.trim() !== "" && flavour.trim() !== "";
  return (
    <Panel title={product ? `Add a flavour to ${product}` : "Add product"} onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (fileId === null) return;
          add.mutate(
            { fileId, name: `${name.trim()} ${flavour.trim()}`, product: name.trim(), variant: flavour.trim() },
            {
              onSuccess: () => {
                toast(product ? `${flavour.trim()} added.` : `${name.trim()} added.`);
                onClose();
              },
            },
          );
        }}
      >
        {!product && <Field label="Product name" placeholder="e.g. Bag" value={name} onChange={(e) => setName(e.target.value)} />}
        <Field label="Flavour" placeholder="e.g. Chicken" value={flavour} onChange={(e) => setFlavour(e.target.value)} />
        <ImagePicker label="Flavour picture" fileId={fileId} onChange={setFileId} />
        {add.isError && <p role="alert" className={errorClass}>{add.error.message}</p>}
        <Button type="submit" busy={add.isPending} disabled={!ready} className="w-full">
          {product ? "Add flavour" : "Add product"}
        </Button>
      </form>
    </Panel>
  );
}

/** Renaming a product renames it on every one of its screens. */
function RenameProduct({ brandId, product, screens, onClose }: { brandId: number; product: string; screens: Screen[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(product);
  const rename = useMutation({
    mutationFn: async () => {
      for (const s of screens) {
        const { error, response } = await api.PATCH("/brands/{brand_id}/screens/{screen_id}", { params: { path: { brand_id: brandId, screen_id: s.id } }, body: { product: name.trim() } });
        if (!response.ok) throw new Error(errorText(error));
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["screens", brandId] });
      toast(`Renamed to ${name.trim()}.`);
      onClose();
    },
  });
  return (
    <Panel title={`Rename ${product}`} onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          rename.mutate();
        }}
      >
        <Field label="Product name" value={name} onChange={(e) => setName(e.target.value)} />
        {rename.isError && <p role="alert" className={errorClass}>{rename.error.message}</p>}
        <Button type="submit" busy={rename.isPending} disabled={!name.trim() || name.trim() === product} className="w-full">
          Rename
        </Button>
      </form>
    </Panel>
  );
}

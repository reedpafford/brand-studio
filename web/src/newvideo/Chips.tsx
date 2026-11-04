import type { ComponentType, ReactNode } from "react";
import { Folder, Users } from "lucide-react";
import { Menu, MenuItem } from "../components";

type Icon = ComponentType<{ size?: number; "aria-hidden"?: boolean; className?: string }>;
const chip = "inline-flex h-[26px] items-center gap-1.5 whitespace-nowrap rounded-sm border border-border-button bg-surface px-2.5 text-xs font-medium hover:bg-surface-2";

/** A setting as a chip, "Format Presenter" (S2): its choices in a menu; `many` toggles several (the cast). */
export function Chip<T extends string | number>({ label, value, options, onPick, icon: I, many, empty = "None" }: { label: string; value: T | T[]; options: { id: T; name: string; off?: string }[]; onPick: (v: T) => void; icon?: Icon; many?: boolean; empty?: string }) {
  const picked = Array.isArray(value) ? value : [value];
  const name = options.filter((o) => picked.includes(o.id)).map((o) => o.name).join(", ") || empty;
  return (
    <Menu
      title={label}
      trigger={(p) => (
        <button type="button" {...p} aria-label={`${label}: ${name}`} className={chip}>
          {I && <I size={12} aria-hidden className="text-muted" />}
          <span className="font-normal text-muted">{label}</span>
          {name}
        </button>
      )}
    >
      {(close) =>
        options.map((o) => (
          <MenuItem key={String(o.id)} checked={picked.includes(o.id)} disabled={!!o.off} onClick={() => (many || close(), onPick(o.id))}>
            <span className="flex-1">{o.name}</span>
            {o.off && <span className="text-sm text-muted">{o.off}</span>}
          </MenuItem>
        ))
      }
    </Menu>
  );
}

/** A setting that comes with its source and can't change here ("Look from the reel"). */
export const FixedChip = ({ label, children }: { label: string; children: ReactNode }) => (
  <span className={`${chip} hover:bg-surface`}>
    <span className="font-normal text-muted">{label}</span>
    {children}
  </span>
);

export const CastIcon = Users;
export const FolderIcon = Folder;

import type { ComponentType } from "react";
import { Menu, MenuItem, chipPress } from "../components";
import type { Mode } from "../newvideo/useNewVideo";

type Icon = ComponentType<{ size?: number; "aria-hidden"?: boolean; className?: string }>;

/** A setting that opens a dialog (Style, Product, Cast): its name alone until something is picked, then name and value. */
export function PickChip({ label, value, none, icon: I, onClick }: { label: string; value: string; /** what a screen reader hears while nothing is picked ("Nobody") */ none: string; icon?: Icon; onClick: () => void }) {
  return (
    <button type="button" aria-haspopup="dialog" aria-label={`${label}: ${value || none}`} onClick={onClick} className={`${chipPress} max-w-full`}>
      {I && <I size={12} aria-hidden className="shrink-0 text-muted" />}
      <span className={value ? "font-normal text-muted" : ""}>{label}</span>
      {value && <span className="min-w-0 truncate">{value}</span>}
    </button>
  );
}

const MODES: { id: Mode; short: string; name: string; line: string }[] = [
  { id: "ask", short: "Ask", name: "Ask before making", line: "You OK the plan and price first" },
  { id: "auto", short: "Auto", name: "Make without asking", line: "It starts as soon as the plan is ready, inside the price shown" },
];

/** "Mode Ask" / "Mode Auto": whether the plan and price wait for an OK. Making without asking is the owner's only. */
export function ModeMenu({ mode, owner, onPick }: { mode: Mode; owner: boolean; onPick: (m: Mode) => void }) {
  const now = MODES.find((m) => m.id === mode) ?? MODES[0];
  return (
    <Menu
      title="Before it starts"
      align="right"
      trigger={(p) => (
        <button type="button" {...p} aria-label={`Mode: ${now.name}`} title={`${now.name}: ${now.line.charAt(0).toLowerCase()}${now.line.slice(1)}`} className={chipPress}>
          <span className="font-normal text-muted">Mode</span>
          {now.short}
        </button>
      )}
    >
      {(close) =>
        MODES.filter((m) => owner || m.id === "ask").map((m) => (
          <MenuItem key={m.id} checked={m.id === mode} onClick={() => (close(), onPick(m.id))}>
            <span className="flex flex-col py-1.5">
              <span className="font-medium">{m.name}</span>
              <span className="text-sm text-muted">{m.line}</span>
            </span>
          </MenuItem>
        ))
      }
    </Menu>
  );
}

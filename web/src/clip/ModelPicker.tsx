import { ChevronDown } from "lucide-react";
import { Menu, MenuItem } from "../components";
import { fromRate, type Model } from "./logic";

const range = (m: Model) =>
  `${m.duration ? `${m.duration.min}–${m.duration.max}s` : "any length"} · up to ${m.resolutions.at(-1)}`;

/** A select-style button that opens the list of models: a popover on desktop, a sheet on a phone. No provider names. */
export function ModelPicker(props: { models: Model[]; value: Model; onChange: (m: Model) => void }) {
  return (
    <Menu
      title="Model"
      trigger={(t) => (
        <button type="button" {...t} aria-label={`Model: ${props.value.name}`} className="flex min-h-control w-full items-center gap-3 rounded-md border border-border bg-surface-2 px-3 text-left hover:bg-surface-3">
          <span className="min-w-0 flex-1 py-2">
            <span className="block font-medium">{props.value.name}</span>
            <span className="block text-sm text-muted">{range(props.value)}</span>
          </span>
          <ChevronDown size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
        </button>
      )}
    >
      {(close) =>
        props.models.map((m) => (
          <MenuItem
            key={m.id}
            checked={m.id === props.value.id}
            onClick={() => {
              props.onChange(m);
              close();
            }}
          >
            <span className="block py-2">
              <span className="block font-medium">{m.name}</span>
              <span className="block text-sm text-muted">
                {range(m)} · from {Math.round(fromRate(m) * 10) / 10} credits a second
              </span>
            </span>
          </MenuItem>
        ))
      }
    </Menu>
  );
}

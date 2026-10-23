import { useState } from "react";
import { input } from "../ui";
import { fromRate, type Model } from "./logic";

const range = (m: Model) =>
  `${m.duration ? `${m.duration.min}–${m.duration.max}s` : "any length"} · up to ${m.resolutions.at(-1)}`;

export function ModelPicker(props: { models: Model[]; value: Model; onChange: (m: Model) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button type="button" aria-haspopup="listbox" aria-expanded={open} className={`${input} min-h-11 text-left`} onClick={() => setOpen(!open)}>
        <span className="block font-medium">{props.value.name}</span>
        <span className="block text-sm text-muted">{range(props.value)}</span>
      </button>
      {open && (
        <ul role="listbox" aria-label="Model" className="absolute z-10 mt-1 w-full rounded-md border border-border bg-surface p-1 shadow-md">
          {props.models.map((m) => (
            <li key={m.id} role="option" aria-selected={m.id === props.value.id}>
              <button
                type="button"
                className={`w-full rounded-sm px-3 py-2 text-left ${m.id === props.value.id ? "bg-accent-soft text-accent-text" : ""}`}
                onClick={() => {
                  props.onChange(m);
                  setOpen(false);
                }}
              >
                <span className="block font-medium">{m.name}</span>
                <span className="block text-sm text-muted">
                  {range(m)} · from {Math.round(fromRate(m) * 10) / 10} credits/s
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

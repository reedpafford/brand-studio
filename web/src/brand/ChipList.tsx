import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "../components";

/** A list of short words as chips with an X, and a box to add another. */
export function ChipList(props: { label: string; items: string[]; onChange: (items: string[]) => void; placeholder?: string; hint?: string }) {
  const [text, setText] = useState("");
  const add = () => {
    const v = text.trim();
    if (v && !props.items.includes(v)) props.onChange([...props.items, v]);
    setText("");
  };
  return (
    <fieldset className="min-w-0 space-y-2">
      <legend className="text-sm font-medium">{props.label}</legend>
      {props.items.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {props.items.map((item) => (
            <li key={item} className="flex items-center gap-1 rounded-md bg-surface-3 pl-3 text-sm">
              {item}
              <button type="button" aria-label={`Remove ${item}`} className="grid size-control place-items-center rounded-md hover:bg-surface-2 lg:size-control-dense" onClick={() => props.onChange(props.items.filter((x) => x !== item))}>
                <X size={16} strokeWidth={1.75} aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input
          className="min-h-control min-w-0 flex-1 rounded-md border border-border-strong bg-surface px-3 text-base text-text placeholder:text-muted"
          aria-label={`Add to ${props.label.toLowerCase()}`}
          placeholder={props.placeholder}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={add} // words typed but not added are kept when you move on (or press Save)
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button variant="secondary" icon={Plus} aria-label={`Add ${props.label.toLowerCase()}`} disabled={!text.trim()} onClick={add}>
          Add
        </Button>
      </div>
      {props.hint && <p className="text-sm text-muted">{props.hint}</p>}
    </fieldset>
  );
}

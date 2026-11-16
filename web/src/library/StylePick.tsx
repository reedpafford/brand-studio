import { useState } from "react";
import { useLooks } from "../scripts/Looks";

const key = (brandId: number) => `bs.style.${brandId}`;

/** The style a Cast & places picture is drawn in: the person picks it, never House by assumption (Reed, 15 Nov). The
 *  pick is remembered for the brand on this computer, so a Movie brand's next person starts on Movie. */
export function useStyle(brandId: number): [string, (id: string) => void] {
  const [style, setStyle] = useState(() => {
    try {
      return localStorage.getItem(key(brandId)) ?? "";
    } catch {
      return ""; // private mode: nothing is remembered, so it's picked each time
    }
  });
  const pick = (id: string) => {
    setStyle(id);
    try {
      localStorage.setItem(key(brandId), id);
    } catch {
      /* private mode: nothing to remember */
    }
  };
  return [style, pick];
}

/** The site's styles as one small list; nothing is picked until the person picks. */
export function StylePick({ value, onPick, disabled, className }: { value: string; onPick: (id: string) => void; disabled?: boolean; className?: string }) {
  const looks = useLooks().data ?? [];
  return (
    <select aria-label="Style" value={looks.some((l) => l.id === value) ? value : ""} disabled={disabled} className={className} onChange={(e) => onPick(e.target.value)}>
      <option value="" disabled>
        Pick a style
      </option>
      {looks.map((l) => (
        <option key={l.id} value={l.id}>
          {l.name}
        </option>
      ))}
    </select>
  );
}

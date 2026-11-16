import { useState } from "react";
import { useMe } from "../auth/useMe";
import { useLooks } from "../scripts/Looks";

const key = (brandId: number) => `bs.style.${brandId}`;

function remembered(brandId: number) {
  try {
    return localStorage.getItem(key(brandId)) ?? "";
  } catch {
    return ""; // private mode: nothing is remembered, so it's picked each time
  }
}

/** The style a Cast & places picture is drawn in: the person picks it, never House by assumption (Reed, 15 Nov). The
 *  pick is remembered for the brand on this computer, so a Movie brand's next person starts on Movie. Only ever a style
 *  the list has now: one since removed reads as none picked, so nothing is sent with it. */
export function useStyle(brandId: number): [string, (id: string) => void] {
  const looks = useLooks().data ?? [];
  const [picked, setPicked] = useState<{ brandId: number; id: string } | null>(null);
  const style = picked?.brandId === brandId ? picked.id : remembered(brandId);
  const pick = (id: string) => {
    setPicked({ brandId, id });
    try {
      localStorage.setItem(key(brandId), id);
    } catch {
      /* private mode: nothing to remember */
    }
  };
  return [looks.some((l) => l.id === style) ? style : "", pick];
}

/** The site's styles as one small list; nothing is picked until the person picks. One switched off is greyed for an
 *  editor (the server refuses it); the owner may pick any. */
export function StylePick({ value, onPick, disabled, className }: { value: string; onPick: (id: string) => void; disabled?: boolean; className?: string }) {
  const looks = useLooks().data ?? [];
  const owner = useMe().data?.role === "owner";
  return (
    <select aria-label="Style" value={value} disabled={disabled} className={className} onChange={(e) => onPick(e.target.value)}>
      <option value="" disabled>
        Pick a style
      </option>
      {looks.map((l) => (
        <option key={l.id} value={l.id} disabled={!owner && !l.on}>
          {l.name}
          {!owner && !l.on ? " (off)" : ""}
        </option>
      ))}
    </select>
  );
}

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Check, CircleAlert } from "lucide-react";
import { Button } from "./Button";

type Kind = "success" | "error";
type Item = { message: string; undo?: () => void; kind: Kind; id: number };
type Show = (message: string, undo?: () => void, kind?: Kind) => void;
const Ctx = createContext<Show>(() => {});

export const useToast = () => useContext(Ctx);

/** One line, 4 seconds (8 with Undo); hovering or focusing it pauses the clock. One live region. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [item, setItem] = useState<Item | null>(null);
  // Paused while the pointer is over it OR focus is inside it, each tracked on its own.
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const paused = hovered || focused;
  const seq = useRef(0);
  const show = useCallback<Show>((message, undo, kind = "success") => {
    setItem({ message, undo, kind, id: ++seq.current });
  }, []);
  const id = item?.id;
  const ms = item?.undo ? 8000 : 4000;
  useEffect(() => {
    if (id === undefined || paused) return;
    const t = setTimeout(() => setItem(null), ms);
    return () => clearTimeout(t);
  }, [id, ms, paused]);

  return (
    <Ctx.Provider value={show}>
      {children}
      {/* Always mounted so screen readers announce what appears inside it. */}
      <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-4 bottom-[calc(var(--tabbar-h)+var(--actionbar-h)+env(safe-area-inset-bottom))] z-40 mx-auto max-w-md sm:bottom-6">
        {item && (
          <div
            key={item.id}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            className="pointer-events-auto flex items-center gap-3 rounded-lg bg-surface-3 px-4 py-3 text-base shadow-raised"
          >
            {item.kind === "error" ? <CircleAlert size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-danger" /> : <Check size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-success" />}
            <span className="flex-1">{item.message}</span>
            {item.undo && (
              <Button
                variant="ghost"
                dense
                onClick={() => {
                  item.undo?.();
                  setItem(null);
                  setHovered(false);
                  setFocused(false);
                }}
              >
                Undo
              </Button>
            )}
          </div>
        )}
      </div>
    </Ctx.Provider>
  );
}

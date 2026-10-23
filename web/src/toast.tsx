import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { btnSecondary } from "./ui";

type Toast = { message: string; undo?: () => void };
const Ctx = createContext<(message: string, undo?: () => void) => void>(() => {});

export const useToast = () => useContext(Ctx);

/** One line at the bottom centre for 4 seconds, with an optional Undo. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const show = useCallback((message: string, undo?: () => void) => {
    clearTimeout(timer.current);
    setToast({ message, undo });
    timer.current = setTimeout(() => setToast(null), 4000);
  }, []);

  return (
    <Ctx.Provider value={show}>
      {children}
      {/* Always mounted so screen readers announce what appears inside it. */}
      <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-4 bottom-[calc(5rem+env(safe-area-inset-bottom))] z-20 mx-auto max-w-md sm:bottom-6">
        {toast && (
          <div className="pointer-events-auto flex items-center gap-3 rounded-md border border-border bg-surface px-4 py-3 text-sm shadow-md">
            <span className="flex-1">{toast.message}</span>
            {toast.undo && (
              <button
                className={btnSecondary}
                onClick={() => {
                  toast.undo?.();
                  setToast(null);
                }}
              >
                Undo
              </button>
            )}
          </div>
        )}
      </div>
    </Ctx.Provider>
  );
}

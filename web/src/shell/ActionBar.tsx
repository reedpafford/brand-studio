import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

type Slot = { node: HTMLElement | null; count: number; setNode: (n: HTMLElement | null) => void; bump: (by: number) => void };
const Ctx = createContext<Slot>({ node: null, count: 0, setNode: () => {}, bump: () => {} });

export function ActionBarProvider({ children }: { children: ReactNode }) {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const [count, setCount] = useState(0);
  const bump = useCallback((by: number) => setCount((n) => n + by), []);
  const value = useMemo(() => ({ node, count, setNode, bump }), [node, count, bump]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** The phone's action bar slot (above the tabs): the page's one amber button goes in it. */
export function useActionBarSlot() {
  return useContext(Ctx);
}

/** A page puts its one amber button here. On a phone it shows in the bar above the tabs; on desktop it renders in place. */
export function ActionBar({ children, phone }: { children: ReactNode; phone: boolean }) {
  const { node, bump } = useContext(Ctx);
  useEffect(() => {
    if (!phone) return;
    bump(1);
    return () => bump(-1);
  }, [phone, bump]);
  if (!phone) return <>{children}</>;
  return node ? createPortal(<div className="border-t border-border bg-surface px-4 py-3">{children}</div>, node) : null;
}

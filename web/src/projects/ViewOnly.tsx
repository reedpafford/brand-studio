import { createContext, useContext, type ReactNode } from "react";

const Ctx = createContext(false);

/** True inside a video only its maker or the owner may change (Builder-Server-8's 403s): the page is for looking. */
export const useViewOnly = () => useContext(Ctx);

/** Greys out every press inside while `on` (a disabled fieldset); links, pictures and native players stay usable. */
export function ViewOnly({ on, children }: { on: boolean; children: ReactNode }) {
  return (
    <Ctx.Provider value={on}>
      <fieldset disabled={on} className="m-0 min-w-0 space-y-4 border-0 p-0">
        {children}
      </fieldset>
    </Ctx.Provider>
  );
}

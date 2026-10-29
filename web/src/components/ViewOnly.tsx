import { createContext, useContext, type ReactNode } from "react";

const Ctx = createContext(false);

/** True inside a video only its maker or the owner may change (the server refuses everyone else): the page is for looking. */
export const useViewOnly = () => useContext(Ctx);

/** Inside, every Button, menu row and form field is greyed out, except presses that only show something (`reads`, or a
 *  Button that opens and closes a part of the page). Links, pictures and players stay as they are. */
export function ViewOnly({ on, children }: { on: boolean; children: ReactNode }) {
  return <Ctx.Provider value={on}>{children}</Ctx.Provider>;
}

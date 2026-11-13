const KEY = "bs.ui";

/** Whether this computer uses the new look, the studio at /s/: it does unless it was sent back to the current site
 *  (the studio's "Back to the current site"; the current Settings' "Open the new look" undoes that). */
export function newLook() {
  try {
    return localStorage.getItem(KEY) !== "old";
  } catch {
    return true; // private mode: nothing is remembered, so the default
  }
}

/** Back to the new look (from the current Settings), or off it (the studio's "Back to the current site"). */
export function setNewLook(on: boolean) {
  try {
    if (on) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, "old");
  } catch {
    /* private mode: nothing to remember */
  }
}

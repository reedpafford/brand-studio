const KEY = "bs.ui";

/** Whether this computer is set to the new look (Settings › "Try the new look"): "/" then opens the studio at /s/. */
export function newLook() {
  try {
    return localStorage.getItem(KEY) === "new";
  } catch {
    return false; // private mode: the current site
  }
}

/** Turns the new look on (from Settings) or off (the studio's "Back to the current site"). */
export function setNewLook(on: boolean) {
  try {
    if (on) localStorage.setItem(KEY, "new");
    else localStorage.removeItem(KEY);
  } catch {
    /* private mode: nothing to remember */
  }
}

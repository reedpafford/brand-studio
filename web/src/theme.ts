export type Theme = "dark" | "light" | "system";
const KEY = "bs.theme";
const ORDER: Theme[] = ["dark", "light", "system"];

/** Dark is the default; "system" follows the computer only when the person picks it. */
export function getTheme(): Theme {
  try {
    const t = localStorage.getItem(KEY);
    return t === "light" || t === "system" ? t : "dark";
  } catch {
    return "dark";
  }
}

/** Sets data-theme on the page (dark, light or system) and remembers the choice. */
export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* not remembering is fine */
  }
}

export const nextTheme = (t: Theme): Theme => ORDER[(ORDER.indexOf(t) + 1) % ORDER.length];

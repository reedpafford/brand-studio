import { afterEach, expect, test } from "vitest";
import { applyTheme, getTheme } from "./theme";

afterEach(() => {
  localStorage.removeItem("bs.theme");
  document.documentElement.removeAttribute("data-theme");
});

test("dark is the default, and an old stored value that is not light or system means dark", () => {
  expect(getTheme()).toBe("dark");
  localStorage.setItem("bs.theme", "dark");
  expect(getTheme()).toBe("dark");
  localStorage.setItem("bs.theme", "nonsense");
  expect(getTheme()).toBe("dark");
});

test("light and system are remembered and set on the page", () => {
  applyTheme("light");
  expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  expect(getTheme()).toBe("light");
  applyTheme("system");
  expect(document.documentElement.getAttribute("data-theme")).toBe("system");
  expect(getTheme()).toBe("system");
});

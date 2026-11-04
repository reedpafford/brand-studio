import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import type { components } from "../api/schema";
import { fakeServer } from "../test/server";
import { TakeSound } from "./TakeSound";

afterEach(() => vi.unstubAllGlobals());

const clip = (sound: object) => ({ id: 5, clip_id: "c2", sound: { state: "none", how: "", asked: "", error: "", credits: 0.06, ...sound } }) as unknown as components["schemas"]["ProjectClipOut"];
const show = (c: components["schemas"]["ProjectClipOut"]) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TakeSound projectId={9} clip={c} />
    </QueryClientProvider>,
  );

test("sound effects are asked for in plain words at their price, and an added sound can be removed", async () => {
  const calls = fakeServer({ "POST /projects/9/clips/5/sound": [201, {}], "DELETE /projects/9/clips/5/sound": [200, {}] });
  const { unmount } = show(clip({}));
  await userEvent.click(screen.getByRole("button", { name: "Add sound effects" }));
  await userEvent.type(screen.getByRole("textbox", { name: "Sound effects for c2" }), "slight footsteps");
  const add = screen.getByRole("button", { name: /^Add/ });
  expect(add).toHaveTextContent("up to 1 credit");
  await userEvent.click(add);
  await waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/5/sound")?.body).toEqual({ asked: "slight footsteps" }));
  unmount();
  show(clip({ state: "ready", how: "slight" }));
  expect(screen.getByText("Sound added · slight")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Remove sound" }));
  await waitFor(() => expect(calls.some((c) => c.key === "DELETE /projects/9/clips/5/sound")).toBe(true));
});

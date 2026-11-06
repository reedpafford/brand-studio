import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { PaneBoundary } from "./PaneBoundary";
import { Filmstrip } from "./RunCard";

function Broken(): never {
  throw new TypeError("undefined is not iterable");
}

test("a tab that breaks says so in its own place, with Try again; the page around it stays", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  const { rerender } = render(
    <div>
      <p>The chat</p>
      <PaneBoundary tab="clips">
        <Broken />
      </PaneBoundary>
    </div>,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("This tab couldn’t show this video");
  expect(screen.getByText("The chat")).toBeInTheDocument();
  rerender(
    <div>
      <p>The chat</p>
      <PaneBoundary tab="cut">
        <p>The cut</p>
      </PaneBoundary>
    </div>,
  );
  expect(screen.getByText("The cut")).toBeInTheDocument(); // another tab: tried afresh
  expect(screen.queryByRole("alert")).toBeNull();
});

test("the console says which tab broke (QA on #1379), and a clip too long for its model is never drawn as done", async () => {
  const said = vi.spyOn(console, "error").mockImplementation(() => {});
  render(
    <PaneBoundary tab="clips">
      <Broken />
    </PaneBoundary>,
  );
  expect(said.mock.calls.some((c) => c[0] === "The clips tab couldn't show this video")).toBe(true);
  const cell = (state: string) => ({ clip_id: `c-${state}`, number: 1, scene: 1, label: "", seconds: 16, model: "Seedance 2.0", state, frame_file_id: 101, take_id: 201, note: "", percent: null, minutes_left: null, credits: null, changed: false, watched: false, found: false });
  const { container } = render(<Filmstrip scenes={[{ id: 1, name: "Hook", total: 2, done: 0, clips: [cell("too_long"), cell("done")] as never }]} />);
  const [long, done] = [...container.querySelectorAll("img")];
  expect(long.className).toContain("outline-danger");
  expect(done.className).not.toContain("outline-danger");
});

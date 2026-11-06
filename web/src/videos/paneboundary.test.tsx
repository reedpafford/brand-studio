import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { PaneBoundary } from "./PaneBoundary";

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

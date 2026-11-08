import { expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ByFormat } from "./ByFormat";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

test("Polish: the format and style table names each pair as the pickers do, and rounds the rate", async () => {
  setViewport(1440);
  fakeServer({
    "GET /usage/by-format-and-style": [200, [{ format: "dialogue", look: "house", videos: 1, credits_per_second: 14.419, redo_rate: 2, average_score: null }]],
    "GET /formats": [200, [{ id: "dialogue", name: "Dialogue", order: 1, engine: "story", blurb: "", on: true }]],
    "GET /looks": [200, [{ id: "house", name: "House", blurb: "", on: true, lanes: [] }]],
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ByFormat />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("rowheader", { name: "Dialogue · House" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "14.4" })).toBeInTheDocument();
  expect(screen.queryByText("dialogue · house")).toBeNull();
  expect(screen.queryByText("14.419")).toBeNull();
});

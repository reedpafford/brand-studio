import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { HostPieces } from "./HostPieces";

afterEach(() => vi.unstubAllGlobals());

const piece = (o: object) => ({ number: 1, start: 0, end: 11.2, state: "ready", file_id: 41, earlier: [], error: null, credits: 2.28, ...o });
const show = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <HostPieces projectId={9} aspect="9:16" />
    </QueryClientProvider>,
  );

test("a presenter's host shows like takes: a failed piece says why and makes again at its price", async () => {
  const host = { on: true, state: "failed", credits: 2, pieces: [piece({ number: 0, file_id: 40, credits: 5 }), piece({}), piece({ number: 2, start: 11.2, end: 20, state: "failed", file_id: null, error: "The video service failed." })] };
  const calls = fakeServer({ "GET /projects/9/host": [200, host], "POST /projects/9/host/2": [201, host] });
  show();
  expect(await screen.findByRole("list", { name: "Host pieces" })).toBeInTheDocument();
  expect(screen.getByText("Didn't finish: The video service failed.")).toBeInTheDocument();
  const again = screen.getAllByRole("button", { name: /Make again/ });
  expect(again[2]).toHaveTextContent("3 credits");
  await userEvent.click(again[2]);
  await waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/host/2")).toBe(true));
});

test("a video with no host shows nothing", async () => {
  const calls = fakeServer({ "GET /projects/9/host": [200, { on: false, state: "none", credits: 0, pieces: [] }] });
  const { container } = show();
  await waitFor(() => expect(calls.length).toBeGreaterThan(0));
  expect(container).toBeEmptyDOMElement();
});

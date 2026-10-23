import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 60, credits_used: 0, budget_pct: 0,
};
const v2 = { version: 2, source: "upload", words: 12, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "SCENE 1 — KITCHEN\nMIA: Wait… it dipped?" };
const v1 = { version: 1, source: "paste", words: 3, created_by_id: 2, created_at: "2026-10-22T10:00:00Z", text: "First draft line" };
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
};

function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/projects/9?tab=script"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("with no script yet you can paste one and it is saved as a version", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/script": [404, { detail: "This project has no script yet." }], "PUT /projects/9/script": [200, v1] });
  open();
  expect(await screen.findByText("No script yet.")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Your script"), "MIA: Wait… it dipped?");
  await userEvent.click(screen.getByRole("button", { name: "Save script" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/script")).toBe(true));
  expect(calls.find((c) => c.key === "PUT /projects/9/script")?.body).toEqual({ text: "MIA: Wait… it dipped?" });
});

test("the script shows line by line with its version, words and source", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [200, v2] });
  open();
  const lines = await screen.findByRole("list", { name: "Script text" });
  expect(within(lines).getAllByRole("listitem")).toHaveLength(2);
  expect(within(lines).getByText("MIA: Wait… it dipped?")).toBeInTheDocument();
  expect(screen.getByText(/v2 · 12 words · uploaded · saved/)).toBeInTheDocument();
});

test("a document upload becomes a new version, and a refused one shows the reason", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/script": [200, v2], "POST /projects/9/script/upload": [422, { detail: "That PDF looks like a scan, so there is no text to read." }] });
  open();
  await userEvent.upload(await screen.findByLabelText("Script file"), new File(["x"], "scan.pdf", { type: "application/pdf" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("That PDF looks like a scan, so there is no text to read.");
  expect(calls.some((c) => c.key === "POST /projects/9/script/upload")).toBe(true);
});

test("history lists versions; you can look at an old one and restore it as a new version", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/script": [200, v2],
    "GET /projects/9/script/versions": [200, [v2, v1].map((v) => ({ ...v, text: undefined }))],
    "GET /projects/9/script/versions/1": [200, v1],
    "PUT /projects/9/script": [200, { ...v1, version: 3 }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "History" }));
  await userEvent.click(await screen.findByRole("button", { name: "View v1" }));
  expect(await screen.findByText("First draft line")).toBeInTheDocument();
  expect(screen.getByText(/You are looking at version 1/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Restore v1" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/script")?.body).toEqual({ text: "First draft line" }));
});

test("editing saves the new words as the next version", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/script": [200, v2], "PUT /projects/9/script": [200, { ...v2, version: 3 }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
  const box = screen.getByLabelText("Your script");
  await userEvent.type(box, " Extra.");
  await userEvent.click(screen.getByRole("button", { name: "Save as a new version" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/script")).toBe(true));
  expect(calls.find((c) => c.key === "PUT /projects/9/script")?.body).toEqual({ text: "SCENE 1 — KITCHEN\nMIA: Wait… it dipped? Extra." });
});

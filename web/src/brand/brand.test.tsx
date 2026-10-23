import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

const editor = { id: 2, email: "eli@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const brand = { id: 1, name: "fomo", slug: "fomo", colours: ["#112233"], fonts: ["Inter"], tone_notes: "Punchy", never_say: [], legal_line: "", logo_file_id: null };

function renderAt(path: string) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("saving the kit sends the edited fields", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, [brand]],
    "PATCH /brands/1": [200, brand],
  });
  renderAt("/b/1/kit");
  const tone = await screen.findByLabelText("Tone of voice");
  await userEvent.clear(tone);
  await userEvent.type(tone, "Calm");
  await userEvent.click(screen.getByRole("button", { name: "Add colour" }));
  await userEvent.click(screen.getByRole("button", { name: "Save kit" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Saved.");
  expect(calls.find((c) => c.key === "PATCH /brands/1")?.body).toMatchObject({
    name: "fomo",
    tone_notes: "Calm",
    fonts: ["Inter"],
    colours: ["#112233", "#000000"],
  });
});

test("adding a screen uploads the picture, then saves it with its tags", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, [brand]],
    "GET /brands/1/screens": [200, []],
    "POST /files": [201, { id: 9, filename: "home.png", content_type: "image/png", size: 3, created_at: "2026-10-23T00:00:00Z" }],
    "POST /brands/1/screens": [201, { id: 4, name: "home", file_id: 9, tags: ["trading"], default_for: ["fomo-moment"], brand_id: 1 }],
  });
  renderAt("/b/1/screens");
  await userEvent.upload(await screen.findByLabelText("Screen image"), new File(["x"], "home.png", { type: "image/png" }));
  await userEvent.type(screen.getByLabelText(/What it shows/), "Trading");
  await userEvent.type(screen.getByLabelText(/moments/), "fomo-moment");
  await userEvent.click(screen.getByRole("button", { name: "Add screen" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/screens")).toBe(true));
  expect(calls.find((c) => c.key === "POST /brands/1/screens")?.body).toEqual({
    name: "home",
    file_id: 9,
    tags: ["trading"],
    default_for: ["fomo-moment"],
  });
});

test("a refused upload shows the server's reason", async () => {
  fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, [brand]],
    "GET /brands/1/screens": [200, []],
    "POST /files": [415, { detail: "That file type isn't supported." }],
  });
  renderAt("/b/1/screens");
  await userEvent.upload(await screen.findByLabelText("Screen image"), new File(["x"], "a.png", { type: "image/png" }));
  await userEvent.click(screen.getByRole("button", { name: "Add screen" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("That file type isn't supported.");
});

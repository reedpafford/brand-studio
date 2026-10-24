import { render, screen, within } from "@testing-library/react";
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
  await userEvent.clear(screen.getByLabelText("Colour 2"));
  await userEvent.type(screen.getByLabelText("Colour 2"), "#000001");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "PATCH /brands/1")?.body).toMatchObject({
    name: "fomo",
    tone_notes: "Calm",
    fonts: ["Inter"],
    colours: ["#112233", "#000001"],
  });
});

test("a bad colour code is explained and blocks saving", async () => {
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, [brand]] });
  renderAt("/b/1/kit");
  const hex = await screen.findByLabelText("Colour 1");
  await userEvent.clear(hex);
  await userEvent.type(hex, "red");
  expect(screen.getByText("Use a colour like #12A150.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
});

test("save is disabled until something changes", async () => {
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, [brand]] });
  renderAt("/b/1/kit");
  const save = await screen.findByRole("button", { name: "Save changes" });
  expect(save).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Legal line"), "Not advice");
  expect(save).toBeEnabled();
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
  await userEvent.click(await screen.findByRole("button", { name: "Add screen" }));
  await userEvent.upload(await screen.findByLabelText("Screen image"), new File(["x"], "home.png", { type: "image/png" }));
  await userEvent.type(screen.getByLabelText(/What it shows/), "Trading");
  await userEvent.type(screen.getByLabelText(/moments/), "Fomo Moment");
  await userEvent.click(screen.getByRole("button", { name: "Save screen" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/screens")).toBe(true));
  expect(calls.find((c) => c.key === "POST /brands/1/screens")?.body).toEqual({
    name: "home",
    file_id: 9,
    tags: ["trading"],
    default_for: ["fomo-moment"],
    product: "",
    variant: "",
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
  await userEvent.click(await screen.findByRole("button", { name: "Add screen" }));
  await userEvent.upload(await screen.findByLabelText("Screen image"), new File(["x"], "a.png", { type: "image/png" }));
  await userEvent.click(screen.getByRole("button", { name: "Save screen" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("That file type isn't supported.");
});

test("a screen can be a flavour of a product, and its product and variant are sent", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, [brand]],
    "GET /brands/1/screens": [200, []],
    "POST /files": [201, { id: 9, filename: "bag.png", content_type: "image/png", size: 3, created_at: "2026-10-23T00:00:00Z" }],
    "POST /brands/1/screens": [201, { id: 4, name: "bag", file_id: 9, tags: [], default_for: [], product: "bag", variant: "Chicken", brand_id: 1 }],
  });
  renderAt("/b/1/screens");
  await userEvent.click(await screen.findByRole("button", { name: "Add screen" }));
  await userEvent.upload(await screen.findByLabelText("Screen image"), new File(["x"], "bag.png", { type: "image/png" }));
  await userEvent.type(screen.getByLabelText(/Product/), "bag");
  await userEvent.type(screen.getByLabelText(/Variant/), "Chicken");
  await userEvent.click(screen.getByRole("button", { name: "Save screen" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands/1/screens")?.body).toMatchObject({ product: "bag", variant: "Chicken" }));
});

test("Edit opens a sheet with the screen's words and saves the changes, product and variant included", async () => {
  const bag = { id: 4, name: "Chicken bag", file_id: 9, tags: ["bag"], default_for: [], product: "bag", variant: "Chicken", brand_id: 1 };
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, [brand]],
    "GET /brands/1/screens": [200, [bag]],
    "PATCH /brands/1/screens/4": [200, bag],
  });
  renderAt("/b/1/screens");
  expect(await screen.findByText("bag · Chicken")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit Chicken bag" }));
  const dialog = await screen.findByRole("dialog", { name: "Edit Chicken bag" });
  const variant = within(dialog).getByLabelText(/Variant/);
  expect(variant).toHaveValue("Chicken");
  // A form sheet's close button doesn't save, so it says Cancel, not Done.
  expect(within(dialog).getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  expect(within(dialog).queryByRole("button", { name: "Done" })).not.toBeInTheDocument();
  await userEvent.clear(variant);
  await userEvent.type(variant, "Peanut butter");
  await userEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /brands/1/screens/4")?.body).toMatchObject({ product: "bag", variant: "Peanut butter", tags: ["bag"] }));
});

test("the End line is shown and saved with the kit", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, [{ ...brand, end_line: "Download fomo through the link in my bio." }]],
    "PATCH /brands/1": [200, brand],
  });
  renderAt("/b/1/kit");
  const end = await screen.findByLabelText(/End line/);
  expect(end).toHaveValue("Download fomo through the link in my bio.");
  await userEvent.clear(end);
  await userEvent.type(end, "Link in bio.");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /brands/1")?.body).toMatchObject({ end_line: "Link in bio." }));
});

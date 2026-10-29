import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";

const owner = { id: 1, email: "o@b.co", name: "Olu", role: "owner", workspace_id: 1 };
const editor = { id: 2, email: "eli@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const lines = [
  { id: "a", text: "Find us through the link in my bio.", default: true },
  { id: "b", text: "Try Iron Paws today.", default: false },
];
const setup = {
  audience: "Dog owners", do_list: ["Say the flavour"], dont_list: ["cure"], music_style: "Upbeat pop", default_language: "en", default_look: "house",
  default_cast: [5, 6], cta_lines: lines, cast: [{ id: 5, name: "Bo", deleted: false }, { id: 6, name: "Max", deleted: true }], advice: [],
};
const brand = { id: 1, name: "fomo", slug: "fomo", colours: ["#112233"], fonts: ["Inter"], tone_notes: "Punchy", never_say: ["cure"], legal_line: "", end_line: lines[0].text, logo_file_id: null, ...setup };
const looks = [{ id: "house", name: "House", blurb: "", on: true }, { id: "pixar", name: "Disney Pixar", blurb: "", on: false }];
const character = (id: number, name: string, o: object = {}) => ({ id, kind: "character", name, owner_project_id: null, owner_script_id: null, ...o });
const routes = (me: object, b: object = brand) => ({
  "GET /auth/me": [200, me] as [number, unknown],
  "GET /brands": [200, [b]] as [number, unknown],
  "GET /looks": [200, looks] as [number, unknown],
  "GET /library/character": [200, [character(5, "Bo"), character(7, "Mia"), character(8, "Own look", { owner_project_id: 3 })]] as [number, unknown],
  "GET /brands/1/screens": [200, []] as [number, unknown],
});

function renderAt(path: string) {
  renderApp(path);
}

afterEach(() => vi.unstubAllGlobals());

test("the owner edits voice and tone and the defaults; one save sends them, never main's never_say or end_line", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...routes(owner), "PATCH /brands/1": [200, brand] });
  renderAt("/b/1/brand");
  expect(await screen.findByText("Changes apply to work from now on. Nothing already made changes.")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Audience"), ", busy ones");
  await userEvent.type(screen.getByLabelText("Add to do"), "Show the bag{Enter}");
  await userEvent.selectOptions(screen.getByLabelText("Look"), "pixar");
  expect(screen.getByText("Off for editors: new scripts will start on House until it's on.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /brands/1")).toBeTruthy());
  const body = calls.find((c) => c.key === "PATCH /brands/1")!.body as Record<string, unknown>;
  expect(body).toMatchObject({ audience: "Dog owners, busy ones", do_list: ["Say the flavour", "Show the bag"], dont_list: ["cure"], default_look: "pixar", default_cast: [5, 6] });
  expect(body).not.toHaveProperty("never_say");
  expect(body).not.toHaveProperty("end_line");
});

test("a deleted default character says so, with Pick another and Remove; only workspace characters are offered", async () => {
  setViewport(390);
  fakeServer(routes(owner));
  renderAt("/b/1/brand");
  expect(await screen.findByText("Deleted: pick another")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Pick another" }));
  const instead = screen.getByLabelText("Instead");
  expect(within(instead).queryByRole("option", { name: "Own look" })).toBeNull();
  await userEvent.selectOptions(instead, "7");
  expect(screen.queryByText("Deleted: pick another")).toBeNull();
  expect(screen.getByText("Mia")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
});

test("CTA lines: deleting the Default says which line is Default now, with Undo; Make default and Add save at once", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...routes(owner),
    "DELETE /brands/1/cta-lines/a": [200, { promoted_id: "b", brand }],
    "POST /brands/1/cta-lines/a/restore": [200, brand],
    "PATCH /brands/1/cta-lines/b": [200, brand],
    "POST /brands/1/cta-lines": [201, brand],
  });
  renderAt("/b/1/brand");
  const list = await screen.findByLabelText("Call to action lines");
  await userEvent.click(within(list).getByRole("button", { name: 'Delete "Find us through the link in my bio."' }));
  expect(await screen.findByText('Deleted. "Try Iron Paws today." is now the Default.')).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/cta-lines/a/restore")).toBe(true));
  await userEvent.click(within(list).getByRole("button", { name: "Make default" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /brands/1/cta-lines/b")?.body).toEqual({ default: true }));
  await userEvent.type(screen.getByLabelText("Add a line"), "Link in bio.");
  await userEvent.click(screen.getByRole("button", { name: "Add line" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands/1/cta-lines")?.body).toEqual({ text: "Link in bio.", default: false }));
});

test("with no characters in Cast & places, Default cast says so and offers a way to add one", async () => {
  setViewport(390);
  fakeServer({ ...routes(owner, { ...brand, default_cast: [], cast: [] }), "GET /library/character": [200, [character(8, "Own look", { owner_project_id: 3 })]] });
  renderAt("/b/1/brand");
  expect(await screen.findByText("No characters yet.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Add one in Cast & places" })).toHaveAttribute("href", "/b/1/library");
  expect(screen.queryByLabelText("Add to the default cast")).toBeNull();
});

test("no CTA line left: the Advice says videos end without one", async () => {
  setViewport(1440);
  fakeServer(routes(owner, { ...brand, cta_lines: [], advice: ["Videos will end without a saved call to action."] }));
  renderAt("/b/1/brand");
  expect(await screen.findByText("Videos will end without a saved call to action.")).toBeInTheDocument();
});

test("an editor keeps what they edit today (tone notes, Don't as never say, End line); only the new sections are read only", async () => {
  setViewport(390);
  const calls = fakeServer({ ...routes(editor), "PATCH /brands/1": [200, brand] });
  renderAt("/b/1/brand");
  expect(await screen.findAllByText("Only the owner changes the brand.")).toHaveLength(2);
  expect(screen.getByLabelText("Audience")).toHaveAttribute("readonly");
  expect(screen.getByLabelText("Music style")).toHaveAttribute("readonly");
  expect(await screen.findByLabelText("Look")).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Add line" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Make default" })).toBeNull();
  expect(screen.queryByLabelText("Add to the default cast")).toBeNull();
  await userEvent.type(screen.getByLabelText("How the brand talks"), ", warm");
  await userEvent.type(screen.getByLabelText("Add to don't"), "miracle{Enter}");
  await userEvent.clear(screen.getByLabelText("End line"));
  await userEvent.type(screen.getByLabelText("End line"), "Link in bio.");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /brands/1")).toBeTruthy());
  const body = calls.find((c) => c.key === "PATCH /brands/1")!.body as Record<string, unknown>;
  expect(body).toMatchObject({ tone_notes: "Punchy, warm", never_say: ["cure", "miracle"], end_line: "Link in bio." });
  for (const k of ["audience", "do_list", "dont_list", "music_style", "default_look", "default_cast"]) expect(body).not.toHaveProperty(k);
});

test("without brand setup on the server the page is as before", async () => {
  setViewport(1440);
  const old = Object.fromEntries(Object.entries(brand).filter(([k]) => !(k in setup)));
  fakeServer(routes(owner, old));
  renderAt("/b/1/brand");
  expect(await screen.findByLabelText("How we sound")).toBeInTheDocument();
  expect(screen.getByLabelText("End line")).toBeInTheDocument();
  expect(screen.queryByText(/Changes apply to work from now on/)).toBeNull();
});

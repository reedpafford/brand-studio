import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const usage = (brand_id: number, name: string, o: object = {}) => ({ brand_id, name, colour: null, archived: false, spend_usd: 28.97, spend_estimated: false, finished: 7, cost_per_finished_usd: null, in_progress: 0, scripts: 0, versions_left: 0, last_activity_at: null, credits: 0, videos: 7, providers: [], ...o });
const look = (id: string, name: string, on: boolean) => ({ id, name, blurb: `${name} blurb.`, card: `${name} line`, broll: "", on, own_sample: false, lanes: [], video_model: "seedance-2.0", test_clip: false, test_still: true, test_tag: false, sample_stand_in: false, formats: [], formats_why: "" });
const BRANDS = [{ id: 1, name: "Palace Guard", colours: ["#ef8a3c"] }, { id: 2, name: "Iron Paws", colours: [] }];
const ROWS = [usage(3, "Night Owl", { archived: true, videos: 0, spend_usd: 0 }), usage(2, "Iron Paws", { videos: 1, spend_usd: 4.12 }), usage(1, "Palace Guard")];

function server(routes: Record<string, [number, unknown]> = {}, me: object = owner) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, BRANDS],
    "GET /workspace": [200, { id: 1, name: "Night Shift Studio" }],
    "GET /usage/brands": [200, { total: 3, next_cursor: null, items: ROWS }],
    "GET /looks": [200, [look("house", "House", true), look("movie", "Movie", true), look("dr-pickle", "Dr. Pickle", false)]],
    "GET /languages": [200, [{ id: "en", name: "English", on: true }, { id: "es", name: "Spanish", on: false }]],
    "PUT /workspace": [200, { id: 1, name: "Reed’s Desk" }],
    "DELETE /brands/2": [204, null],
    "POST /brands/2/restore": [200, BRANDS[1]],
    "POST /brands/3/restore": [200, { id: 3, name: "Night Owl", colours: [] }],
    "PATCH /looks/movie": [200, look("movie", "Movie", false)],
    "PATCH /looks/dr-pickle": [409, { detail: "Make Dr. Pickle’s sample first." }],
    "PATCH /languages/es": [200, { id: "es", name: "Spanish", on: true }],
    ...routes,
  });
}
type Calls = ReturnType<typeof server>;
/** Every request that wasn't a read, as "METHOD /path" with its body. */
const writes = (calls: Calls) => calls.filter((c) => !c.key.startsWith("GET ")).map((c) => [c.key, c.body]);
const brandRow = async (name: string) => within((await screen.findByText(name, { selector: "li b" })).closest("li")!);

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
});
afterEach(() => vi.unstubAllGlobals());

test("the studio name saves when the field is left, only if it changed, and Undo puts the old one back", async () => {
  const calls = server();
  renderApp("/s/settings");
  const name = await screen.findByRole("textbox", { name: "Studio name" });
  await vi.waitFor(() => expect(name).toHaveValue("Night Shift Studio"));
  await userEvent.click(name);
  await userEvent.tab(); // left as it was
  expect(writes(calls)).toEqual([]);
  await userEvent.clear(name);
  await userEvent.type(name, "  Reed’s Desk {Enter}");
  expect(await screen.findByText("Studio name saved.")).toBeInTheDocument();
  expect(writes(calls)).toEqual([["PUT /workspace", { name: "Reed’s Desk" }]]);
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(writes(calls)[1]).toEqual(["PUT /workspace", { name: "Night Shift Studio" }]));
});

test("each brand shows what the server says it made and spent, with the way to its set-up and to a new brand", async () => {
  server();
  renderApp("/s/settings");
  const palace = await brandRow("Palace Guard");
  expect(palace.getByText("7 videos · $28.97 spent so far")).toBeInTheDocument();
  expect(palace.getByRole("link", { name: "Set up Palace Guard" })).toHaveAttribute("href", "/s/b/1/setup");
  expect(screen.getByRole("link", { name: "New brand" })).toHaveAttribute("href", "/s/brands/new");
  await userEvent.click(screen.getByRole("button", { name: "Brand: Palace Guard" }));
  expect(within(screen.getByRole("menu", { name: "Brands" })).getByRole("link", { name: "New brand" })).toHaveAttribute("href", "/s/brands/new");
});

test("Archive asks first and sends nothing until confirmed; then the brand is archived, and Undo brings it back", async () => {
  const calls = server();
  renderApp("/s/settings");
  await userEvent.click((await brandRow("Iron Paws")).getByRole("button", { name: "Archive Iron Paws" }));
  const dialog = within(screen.getByRole("dialog", { name: "Archive Iron Paws?" }));
  expect(dialog.getByText("It leaves the brand menu. Its videos, people and clips are kept, and you can bring it back from here.")).toBeInTheDocument();
  await userEvent.click(dialog.getByRole("button", { name: "Cancel" }));
  expect(writes(calls)).toEqual([]);
  await userEvent.click(screen.getByRole("button", { name: "Archive Iron Paws" }));
  await userEvent.click(screen.getByRole("button", { name: "Archive" }));
  expect(await screen.findByText("Archived Iron Paws.")).toBeInTheDocument();
  expect(writes(calls)).toEqual([["DELETE /brands/2", undefined]]);
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  expect(await screen.findByText("Brought back Iron Paws.")).toBeInTheDocument();
  expect(writes(calls)[1]).toEqual(["POST /brands/2/restore", undefined]);
});

test("a refused archive shows the server's words and changes nothing; an archived brand can be brought back", async () => {
  const calls = server({ "DELETE /brands/2": [403, { detail: "Only the owner archives a brand." }] });
  renderApp("/s/settings");
  await userEvent.click((await brandRow("Iron Paws")).getByRole("button", { name: "Archive Iron Paws" }));
  await userEvent.click(screen.getByRole("button", { name: "Archive" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Couldn’t do that. Nothing changed. Only the owner archives a brand.");
  await userEvent.keyboard("{Escape}");
  const owl = await brandRow("Night Owl");
  expect(owl.getByText(/^Archived · 0 videos/)).toBeInTheDocument();
  await userEvent.click(owl.getByRole("button", { name: "Bring back Night Owl" }));
  expect(await screen.findByText("Brought back Night Owl.")).toBeInTheDocument();
  expect(writes(calls).at(-1)).toEqual(["POST /brands/3/restore", undefined]);
});

test("the only brand has no Archive", async () => {
  server({ "GET /brands": [200, BRANDS.slice(0, 1)], "GET /usage/brands": [200, { total: 1, next_cursor: null, items: [usage(1, "Palace Guard")] }] });
  renderApp("/s/settings");
  const palace = await brandRow("Palace Guard");
  expect(palace.getByRole("link", { name: "Set up Palace Guard" })).toBeInTheDocument();
  expect(palace.queryByRole("button", { name: /Archive/ })).toBeNull();
});

test("a look's switch sends on or off, Undo sends it back, and a refusal shows the server's words; House has no switch", async () => {
  const calls = server();
  renderApp("/s/settings");
  await userEvent.click(await screen.findByRole("switch", { name: "Movie", checked: true }));
  expect(await screen.findByText("Movie is off. Videos using it keep it.")).toBeInTheDocument();
  expect(writes(calls)).toEqual([["PATCH /looks/movie", { on: false }]]);
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(writes(calls)[1]).toEqual(["PATCH /looks/movie", { on: true }]));
  await userEvent.click(screen.getByRole("switch", { name: "Dr. Pickle", checked: false }));
  expect(await screen.findByText("Make Dr. Pickle’s sample first.")).toBeInTheDocument();
  expect(writes(calls)[2]).toEqual(["PATCH /looks/dr-pickle", { on: true }]);
  expect(screen.queryByRole("switch", { name: "House" })).toBeNull();
  expect(screen.getByText("House").closest("li")).toHaveTextContent("Always on");
});

test("a language's switch sends on or off; English has no switch", async () => {
  const calls = server();
  renderApp("/s/settings");
  await userEvent.click(await screen.findByRole("switch", { name: "Spanish", checked: false }));
  expect(await screen.findByText("Spanish is on.")).toBeInTheDocument();
  expect(writes(calls)).toEqual([["PATCH /languages/es", { on: true }]]);
  expect(screen.queryByRole("switch", { name: "English" })).toBeNull();
});

test("Use the current site turns the new look off on this computer and leaves; what Settings leaves out links to the current site", async () => {
  server();
  renderApp("/s/settings");
  for (const [name, to] of [["credit limits", "/settings?tab=limits"], ["the team", "/team"], ["a look’s sample", "/settings?tab=looks"], ["a language’s test script", "/settings?tab=languages"]]) expect(await screen.findByRole("link", { name })).toHaveAttribute("href", to);
  await userEvent.click(screen.getByRole("button", { name: "Use the current site" }));
  expect(localStorage.getItem("bs.ui")).toBe("old");
  expect(await screen.findByRole("button", { name: "Account menu" })).toBeInTheDocument(); // the current site's rail
});

test("Sign out sends the current site's sign-out, once, and opens Sign in", async () => {
  const calls = server({ "POST /auth/logout": [204, null] });
  renderApp("/s/settings");
  await userEvent.dblClick(await screen.findByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in to Brand Studio" })).toBeInTheDocument();
  expect(calls.filter((c) => !c.key.startsWith("GET ")).map((c) => c.key)).toEqual(["POST /auth/logout"]);
});

test("someone who isn't the owner is told Settings is the owner's", async () => {
  const calls = server({}, editor);
  renderApp("/s/settings");
  expect(await screen.findByText("Only the owner manages settings.")).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: "Studio name" })).toBeNull();
  expect(writes(calls)).toEqual([]);
});

test("Settings sends nothing on its own: opening it, moving through it and coming back to the window are only GETs", async () => {
  const calls = server();
  renderApp("/s/settings");
  await brandRow("Palace Guard");
  await screen.findByRole("switch", { name: "Movie" });
  for (let n = 0; n < 12; n++) await userEvent.tab(); // focus passes through the name field and every press
  window.dispatchEvent(new Event("focus"));
  expect(writes(calls)).toEqual([]);
});

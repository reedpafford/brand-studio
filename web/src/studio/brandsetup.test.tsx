import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

// The product's notes as he wrote them: odd spacing, a blank line, a trailing newline. Nothing may tidy them.
const NOTES = "  The ring is the pin.\n\nOne hand holds the body;  the other yanks the ring out.\n";
const BRAND = { id: 1, name: "Palace Guard", slug: "palace-guard", logo_file_id: 7, colours: ["#112233", "#EEEEEE"], tone_notes: "Plain and urgent." };
const MADE = { id: 9, name: "Northwind", slug: "northwind", logo_file_id: null, colours: ["#5AA9E6"], tone_notes: "" };
const product = (o: object = {}) => ({ id: 21, kind: "prop", name: "Protector alarm", notes: NOTES, brand_ids: [1, 4], short_description: null, main_claim: "Loud", product_type: "physical", owner_project_id: null, owner_script_id: null, pictures: [{ screen_id: 5, file_id: 60, name: "Protector alarm", variant: "" }], image_file_ids: [], ...o });
const photo = (name: string) => new File(["x"], name, { type: "image/png" });

function server(routes: Record<string, [number, unknown]> = {}, me: object = owner) {
  const all: Record<string, [number, unknown]> = {
    "GET /auth/me": [200, me],
    "GET /brands": [200, [BRAND]],
    "GET /library/prop": [200, [product()]],
    "POST /brands": [201, MADE],
    "PATCH /brands/1": [200, BRAND],
    "POST /library/prop": [201, product({ id: 30, name: "Compass", notes: "", pictures: [] })],
    "PATCH /library/prop/21": [200, product()],
    "POST /files": [201, { id: 61 }],
    "POST /brands/1/screens": [201, {}],
    "POST /brands/9/screens": [201, {}],
    ...routes,
  };
  return { all, calls: fakeServer(all) };
}
type Calls = ReturnType<typeof server>["calls"];
/** Every request that wasn't a read, as "METHOD /path" with its body (an upload's file is not JSON, so it has none). */
const writes = (calls: Calls) => calls.filter((c) => !c.key.startsWith("GET ")).map((c) => [c.key, c.body]);
const has = (name: string) => within(screen.getByRole("complementary", { name: "What the director has" })).getByText(name).closest("li")!;
const crumb = () => within(screen.getByRole("main")).getByRole("link", { name: "Settings" });
const how = () => screen.findByRole("textbox", { name: "How it works" });

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => {} }));
});
afterEach(() => vi.unstubAllGlobals());

test("a new brand with only a name and a colour sends the brand alone, then opens its empty New video page", async () => {
  const { all, calls } = server();
  renderApp("/s/brands/new");
  const create = await screen.findByRole("button", { name: "Create brand" });
  expect(create).toBeDisabled();
  expect(screen.getByText("Give the brand a name first.")).toBeInTheDocument();
  await userEvent.type(screen.getByRole("textbox", { name: "Brand name" }), " Northwind ");
  await userEvent.click(screen.getByRole("button", { name: "Blue", pressed: false }));
  expect(has("Name and colour")).toHaveTextContent("Name and colour, added");
  expect(has("The product")).not.toHaveTextContent("added");
  all["GET /brands"] = [200, [BRAND, MADE]];
  await userEvent.click(create);
  expect(await screen.findByText("Northwind is ready. Paste a script to make its first video.")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "New video" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Brand: Northwind" })).toBeInTheDocument();
  expect(writes(calls)).toEqual([["POST /brands", { name: "Northwind", logo_file_id: null, colours: ["#5AA9E6"], tone_notes: "" }]]);
});

test("a new brand with a product sends the brand with its tone, the product with how it works exactly as typed, and each photo as its picture", async () => {
  const { all, calls } = server();
  renderApp("/s/brands/new");
  await userEvent.type(await screen.findByRole("textbox", { name: "Brand name" }), "Northwind");
  await userEvent.type(screen.getByRole("textbox", { name: "Tone and rules" }), "Dry. Never shouts.");
  await userEvent.type(await how(), "  You twist the cap.{Enter}");
  expect(screen.getByRole("button", { name: "Create brand" })).toBeDisabled(); // a product needs its name
  expect(screen.getByText("Give the product a name first.")).toBeInTheDocument();
  await userEvent.type(screen.getByRole("textbox", { name: "Product name" }), "Compass");
  await userEvent.upload(screen.getByLabelText("Add photos of the product"), [photo("front.png"), photo("back.png")]);
  for (const name of ["The product", "A photo of it", "How it works", "Tone and rules"]) expect(has(name)).toHaveTextContent("added");
  all["GET /brands"] = [200, [BRAND, MADE]];
  await userEvent.click(screen.getByRole("button", { name: "Create brand" }));
  expect(await screen.findByRole("heading", { name: "New video" })).toBeInTheDocument();
  const picture = (name: string) => ({ name, file_id: 61, tags: ["product"], default_for: ["product"], product_id: 30, variant: "" });
  expect(writes(calls)).toEqual([
    ["POST /brands", { name: "Northwind", logo_file_id: null, colours: ["#EF8A3C"], tone_notes: "Dry. Never shouts." }],
    ["POST /library/prop", { name: "Compass", notes: "  You twist the cap.\n", brand_ids: [9], image_file_ids: [], outfits: [], source_photo_file_id: null, presenter: false, product_type: "physical" }],
    ["POST /files", undefined],
    ["POST /brands/9/screens", picture("Compass")],
    ["POST /files", undefined],
    ["POST /brands/9/screens", picture("Compass (2)")],
  ]);
});

test("when the product is refused after the brand is made, the server's words show and trying again doesn't make a second brand", async () => {
  const { all, calls } = server({ "POST /library/prop": [422, { detail: "That name is taken." }] });
  renderApp("/s/brands/new");
  await userEvent.type(await screen.findByRole("textbox", { name: "Brand name" }), "Northwind");
  await userEvent.type(screen.getByRole("textbox", { name: "Product name" }), "Compass");
  await userEvent.click(screen.getByRole("button", { name: "Create brand" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Northwind is made, but its product is not saved yet. That name is taken.");
  expect(screen.getByRole("textbox", { name: "Brand name" })).toBeDisabled();
  all["POST /library/prop"] = [201, product({ id: 30, name: "Compass", notes: "", pictures: [] })];
  all["GET /brands"] = [200, [BRAND, MADE]];
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("heading", { name: "New video" })).toBeInTheDocument();
  expect(writes(calls).map(([key]) => key)).toEqual(["POST /brands", "POST /library/prop", "POST /library/prop"]);
});

test("a brand's set-up shows what is saved; Save changes sends the name, colour and tone, keeps its logo and other colours, and Undo sends them back", async () => {
  const { calls } = server();
  renderApp("/s/b/1/setup");
  expect(await screen.findByRole("heading", { name: "Set up Palace Guard" })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Brand name" })).toHaveValue("Palace Guard");
  expect(screen.getByRole("button", { name: "The colour it has now", pressed: true })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Teal" }));
  await userEvent.type(screen.getByRole("textbox", { name: "Tone and rules" }), " Never jokes.");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(writes(calls)).toEqual([["PATCH /brands/1", { name: "Palace Guard", logo_file_id: 7, colours: ["#1F9FB5", "#EEEEEE"], tone_notes: "Plain and urgent. Never jokes." }]]);
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(writes(calls)[1]).toEqual(["PATCH /brands/1", { name: "Palace Guard", logo_file_id: 7, colours: ["#112233", "#EEEEEE"], tone_notes: "Plain and urgent." }]));
});

test("How it works is the product's own notes, shown as stored and sent exactly as typed, only on Save", async () => {
  const { calls } = server();
  renderApp("/s/b/1/setup");
  const box = await how();
  expect(box).toHaveValue(NOTES); // not trimmed, split or rewritten on the way in
  expect(screen.getByRole("button", { name: "Save how it works" })).toBeDisabled();
  await userEvent.type(box, "It keeps  flashing. ");
  await userEvent.tab();
  expect(writes(calls)).toEqual([]); // typing and leaving the box send nothing
  await userEvent.click(screen.getByRole("button", { name: "Save how it works" }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(writes(calls)).toEqual([["PATCH /library/prop/21", { name: "Protector alarm", notes: `${NOTES}It keeps  flashing. `, brand_ids: [1, 4], short_description: "", main_claim: "Loud" }]]);
});

test("a photo added to a saved product is uploaded and linked as its next picture", async () => {
  const { calls } = server();
  renderApp("/s/b/1/setup");
  expect(await screen.findByRole("img", { name: "Protector alarm" })).toHaveAttribute("src", "/api/files/60");
  await userEvent.upload(screen.getByLabelText("Add a photo of Protector alarm"), photo("side.png"));
  await vi.waitFor(() => expect(writes(calls)).toEqual([["POST /files", undefined], ["POST /brands/1/screens", { name: "Protector alarm (2)", file_id: 61, tags: ["product"], default_for: ["product"], product_id: 21, variant: "" }]]));
});

test("a brand with no product yet can save one from its set-up", async () => {
  const { calls } = server({ "GET /library/prop": [200, []] });
  renderApp("/s/b/1/setup");
  const save = await screen.findByRole("button", { name: "Save the product" });
  expect(save).toBeDisabled();
  await userEvent.type(screen.getByRole("textbox", { name: "Product name" }), "Compass");
  await userEvent.click(save);
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(writes(calls)).toEqual([["POST /library/prop", { name: "Compass", notes: "", brand_ids: [1], image_file_ids: [], outfits: [], source_photo_file_id: null, presenter: false, product_type: "physical" }]]);
});

test("leaving with something typed and not saved asks first", async () => {
  const { calls } = server();
  renderApp("/s/b/1/setup");
  await userEvent.type(await how(), "More.");
  await userEvent.click(crumb());
  const dialog = within(await screen.findByRole("dialog", { name: "Leave without saving?" }));
  await userEvent.click(dialog.getByRole("button", { name: "Cancel" }));
  expect(await how()).toHaveValue(`${NOTES}More.`);
  await userEvent.click(crumb());
  await userEvent.click(screen.getByRole("button", { name: "Leave" }));
  expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
  expect(writes(calls)).toEqual([]);
});

test("someone who isn't the owner can't set up a brand", async () => {
  server({}, editor);
  renderApp("/s/brands/new");
  expect(await screen.findByText("Only the owner sets up brands.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Create brand" })).toBeNull();
});

test.each(["/s/brands/new", "/s/b/1/setup"])("%s sends nothing on its own: opening it and moving through it are only GETs", async (path) => {
  const { calls } = server();
  renderApp(path);
  await screen.findByRole("textbox", { name: "Brand name" });
  if (path.endsWith("setup")) await screen.findByRole("img", { name: "Protector alarm" });
  for (let n = 0; n < 16; n++) await userEvent.tab(); // focus passes through every field and press
  window.dispatchEvent(new Event("focus"));
  expect(writes(calls)).toEqual([]);
});

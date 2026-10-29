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
  const tone = await screen.findByLabelText("How we sound");
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
  expect(await screen.findByRole("button", { name: "Save changes" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Save changes" })).toHaveAccessibleDescription("No changes yet");
  await userEvent.type(screen.getByLabelText("Legal line"), "Not advice");
  expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
});

const fileRow = { id: 9, filename: "home.png", content_type: "image/png", size: 3, created_at: "2026-10-23T00:00:00Z" };
const bag = { id: 4, name: "Chicken bag", file_id: 9, tags: ["bag"], default_for: [], product: "bag", variant: "Chicken", brand_id: 1 };
const withScreens = (rows: unknown[], more: Record<string, [number, unknown]> = {}) =>
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, [brand]], "GET /brands/1/screens": [200, rows], ...more });

test("Add screens takes several pictures; each is uploaded and saved as a screen named from its file", async () => {
  const calls = withScreens([], { "POST /files": [201, fileRow], "POST /brands/1/screens": [201, { id: 4, name: "home", file_id: 9, tags: [], default_for: [], brand_id: 1 }] });
  renderAt("/b/1/brand?tab=screens");
  await userEvent.click(await screen.findByRole("button", { name: "Add screens" }));
  await userEvent.upload(await screen.findByLabelText("Screen images"), [new File(["x"], "home.png", { type: "image/png" }), new File(["y"], "chart.png", { type: "image/png" })]);
  await userEvent.click(screen.getByRole("button", { name: "Add 2 screens" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /brands/1/screens")).toHaveLength(2));
  expect(calls.filter((c) => c.key === "POST /brands/1/screens").map((c) => c.body)).toEqual([
    { name: "home", file_id: 9, tags: [], default_for: [], product: "", variant: "" },
    { name: "chart", file_id: 9, tags: [], default_for: [], product: "", variant: "" },
  ]);
});

test("a refused upload shows the server's reason under that picture", async () => {
  withScreens([], { "POST /files": [415, { detail: "That file type isn't supported." }] });
  renderAt("/b/1/brand?tab=screens");
  await userEvent.click(await screen.findByRole("button", { name: "Add screens" }));
  await userEvent.upload(await screen.findByLabelText("Screen images"), new File(["x"], "a.png", { type: "image/png" }));
  await userEvent.click(screen.getByRole("button", { name: "Add screen" }));
  expect(await screen.findByText("That file type isn't supported.")).toBeInTheDocument();
});

test("a screen tile opens its editor; tags, moments, product and flavour are saved together", async () => {
  const calls = withScreens([bag], { "PATCH /brands/1/screens/4": [200, bag] });
  renderAt("/b/1/brand?tab=screens");
  await userEvent.click(await screen.findByRole("button", { name: "Chicken bag" }));
  const panel = await screen.findByRole("dialog", { name: "Edit Chicken bag" });
  expect(within(panel).getByLabelText("Flavour")).toHaveValue("Chicken");
  await userEvent.clear(within(panel).getByLabelText("Flavour"));
  await userEvent.type(within(panel).getByLabelText("Flavour"), "Peanut butter");
  await userEvent.type(within(panel).getByLabelText("Add to tags"), "Trading Chart{Enter}");
  await userEvent.type(within(panel).getByLabelText("Add to always use this screen for"), "Buy moment{Enter}");
  await userEvent.click(within(panel).getByRole("button", { name: "Save screen" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /brands/1/screens/4")?.body).toMatchObject({ product: "bag", variant: "Peanut butter", tags: ["bag", "trading-chart"], default_for: ["buy-moment"] }));
});

test("Delete screen closes the panel at once and the toast says how to undo it", async () => {
  const calls = withScreens([bag], { "DELETE /brands/1/screens/4": [204, null], "POST /brands/1/screens/4/restore": [200, {}], "GET /brands/1/screens?deleted=true": [200, []] });
  renderAt("/b/1/brand?tab=screens");
  await userEvent.click(await screen.findByRole("button", { name: "Chicken bag" }));
  await userEvent.click(within(await screen.findByRole("dialog", { name: "Edit Chicken bag" })).getByRole("button", { name: "Delete screen" }));
  expect(await screen.findByText('Deleted "Chicken bag".')).toBeInTheDocument();
  expect(screen.queryByRole("alertdialog")).toBeNull();
  expect(screen.queryByRole("dialog", { name: "Edit Chicken bag" })).toBeNull();
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /brands/1/screens/4")).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/screens/4/restore")).toBe(true));
});

test("Show deleted lists the deleted screens, each with Restore", async () => {
  const gone = { ...bag, id: 7, name: "Old home" };
  const calls = withScreens([bag], { "GET /brands/1/screens?deleted=true": [200, [gone]], "POST /brands/1/screens/7/restore": [200, {}] });
  renderAt("/b/1/brand?tab=screens");
  await userEvent.click(await screen.findByRole("button", { name: "Show deleted (1)" }));
  const list = screen.getByRole("list", { name: "Deleted screens" });
  expect(within(list).getByText("Old home")).toBeInTheDocument();
  await userEvent.click(within(list).getByRole("button", { name: "Restore Old home" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/screens/7/restore")).toBe(true));
  expect(await screen.findByText('Restored "Old home".')).toBeInTheDocument();
});

test("renaming a screen to a deleted screen's name shows the server's words and a Restore button", async () => {
  const gone = { ...bag, id: 7, name: "Old home" };
  const calls = withScreens([bag], {
    "GET /brands/1/screens?deleted=true": [200, [gone]],
    "PATCH /brands/1/screens/4": [409, { detail: "A deleted screen has that name. Restore it, or pick another name." }],
    "POST /brands/1/screens/7/restore": [200, {}],
  });
  renderAt("/b/1/brand?tab=screens");
  await userEvent.click(await screen.findByRole("button", { name: "Chicken bag" }));
  const panel = await screen.findByRole("dialog", { name: "Edit Chicken bag" });
  await userEvent.clear(within(panel).getByLabelText("Name"));
  await userEvent.type(within(panel).getByLabelText("Name"), "Old home");
  await userEvent.click(within(panel).getByRole("button", { name: "Save screen" }));
  expect(await within(panel).findByText("A deleted screen has that name. Restore it, or pick another name.")).toBeInTheDocument();
  await userEvent.click(within(panel).getByRole("button", { name: 'Restore "Old home"' }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/screens/7/restore")).toBe(true));
});

test("a screen always used for a moment says so on its tile", async () => {
  withScreens([{ ...bag, default_for: ["buy-moment"] }]);
  renderAt("/b/1/brand?tab=screens");
  expect(await screen.findByText("buy moment")).toBeInTheDocument();
});

test("Products groups screens by product and lists their flavours; renaming a product renames it on every screen", async () => {
  const peanut = { ...bag, id: 5, name: "Peanut bag", variant: "Peanut butter" };
  const calls = withScreens([bag, peanut], { "PATCH /brands/1/screens/4": [200, bag], "PATCH /brands/1/screens/5": [200, peanut] });
  renderAt("/b/1/brand?tab=products");
  expect(await screen.findByRole("heading", { name: /bag/ })).toHaveTextContent("2 flavours");
  expect(screen.getByRole("button", { name: "Chicken" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Peanut butter" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "More for bag" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Rename bag" }));
  const panel = await screen.findByRole("dialog", { name: "Rename bag" });
  await userEvent.clear(within(panel).getByLabelText("Product name"));
  await userEvent.type(within(panel).getByLabelText("Product name"), "Treat bag");
  await userEvent.click(within(panel).getByRole("button", { name: "Rename" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key.startsWith("PATCH /brands/1/screens/"))).toHaveLength(2));
  expect(calls.filter((c) => c.key.startsWith("PATCH")).map((c) => c.body)).toEqual([{ product: "Treat bag" }, { product: "Treat bag" }]);
});

test("Add product takes a name, a first flavour and its picture, and saves it as a screen of that product", async () => {
  const calls = withScreens([], { "POST /files": [201, fileRow], "POST /brands/1/screens": [201, bag] });
  renderAt("/b/1/brand?tab=products");
  expect(await screen.findByText("No products yet.")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Add product" })[0]);
  const panel = await screen.findByRole("dialog", { name: "Add product" });
  await userEvent.type(within(panel).getByLabelText("Product name"), "Bag");
  await userEvent.type(within(panel).getByLabelText("Flavour"), "Chicken");
  await userEvent.upload(within(panel).getByLabelText("Flavour picture file"), new File(["x"], "bag.png", { type: "image/png" }));
  await userEvent.click(within(panel).getByRole("button", { name: "Add product" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands/1/screens")?.body).toMatchObject({ product: "Bag", variant: "Chicken", name: "Bag Chicken" }));
});

test("the End line's example uses the brand's own name (#749 LW10)", async () => {
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, [{ ...brand, name: "Iron Paws", slug: "iron-paws" }]] });
  renderAt("/b/1/kit");
  const end = await screen.findByLabelText(/End line/);
  expect(end).toHaveAccessibleDescription(/Find Iron Paws through the link in my bio/);
  expect(end).not.toHaveAccessibleDescription(/fomo/);
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

test("fonts and never-say words are chips: one can be added and one removed, and both are saved", async () => {
  const calls = fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, [{ ...brand, never_say: ["guaranteed"] }]], "PATCH /brands/1": [200, brand] });
  renderAt("/b/1/brand");
  await userEvent.type(await screen.findByLabelText("Add to fonts"), "Manrope{Enter}");
  await userEvent.click(screen.getByRole("button", { name: "Remove guaranteed" }));
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "PATCH /brands/1")?.body).toMatchObject({ fonts: ["Inter", "Manrope"], never_say: [] });
});

test("leaving Look with unsaved changes asks first; Keep editing stays, Leave goes to App screens", async () => {
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, [brand]], "GET /brands/1/screens": [200, []] });
  renderAt("/b/1/brand");
  await userEvent.type(await screen.findByLabelText("Legal line"), "Not advice");
  await userEvent.click(screen.getByRole("tab", { name: /^App screens/ }));
  const dialog = await screen.findByRole("alertdialog", { name: "Leave without saving?" });
  await userEvent.click(within(dialog).getByRole("button", { name: "Keep editing" }));
  expect(screen.getByLabelText("Legal line")).toHaveValue("Not advice");
  await userEvent.click(screen.getByRole("tab", { name: /^App screens/ }));
  await userEvent.click(within(await screen.findByRole("alertdialog", { name: "Leave without saving?" })).getByRole("button", { name: "Leave" }));
  expect(await screen.findByText("No brand screens yet.")).toBeInTheDocument();
});

test("a never-say word that was typed but not added is kept when you move on, and a reload asks while there are unsaved changes", async () => {
  const calls = fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, [brand]], "PATCH /brands/1": [200, brand] });
  renderAt("/b/1/brand");
  const box = await screen.findByLabelText("Add to never say");
  await userEvent.type(box, "guaranteed");
  await userEvent.tab(); // moving on adds it
  expect(screen.getByRole("button", { name: "Remove guaranteed" })).toBeInTheDocument();
  const ask = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(ask);
  expect(ask.defaultPrevented).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /brands/1")?.body).toMatchObject({ never_say: ["guaranteed"] }));
});

test("Bag and bag are one product, shown with the spelling most screens use; renaming sets one spelling on every screen", async () => {
  const mk = (id: number, product: string, variant: string) => ({ ...bag, id, name: `${variant} ${product}`, product, variant });
  const rows = [mk(4, "Bag", "Chicken"), mk(5, "bag", "Salmon"), mk(6, "Bag", "Peanut butter")];
  const calls = withScreens(rows, { "PATCH /brands/1/screens/4": [200, rows[0]], "PATCH /brands/1/screens/5": [200, rows[1]], "PATCH /brands/1/screens/6": [200, rows[2]] });
  renderAt("/b/1/brand?tab=products");
  expect(await screen.findByRole("heading", { name: /Bag/ })).toHaveTextContent("3 flavours");
  expect(screen.getAllByRole("heading", { level: 2 }).filter((h) => /bag/i.test(h.textContent ?? ""))).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "More for Bag" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Rename Bag" }));
  const panel = await screen.findByRole("dialog", { name: "Rename Bag" });
  await userEvent.clear(within(panel).getByLabelText("Product name"));
  await userEvent.type(within(panel).getByLabelText("Product name"), "Treat bag");
  await userEvent.click(within(panel).getByRole("button", { name: "Rename" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key.startsWith("PATCH /brands/1/screens/"))).toHaveLength(3));
});

test("a tile shows its first moment and how many more", async () => {
  withScreens([{ ...bag, default_for: ["trading", "win"] }]);
  renderAt("/b/1/brand?tab=screens");
  expect(await screen.findByText("trading +1")).toBeInTheDocument();
});

test("the Products tab counts Bag and bag as one product", async () => {
  const mk = (id: number, product: string, variant: string) => ({ ...bag, id, name: `${variant} ${product}`, product, variant });
  withScreens([mk(4, "Bag", "Chicken"), mk(5, "bag", "Salmon")]);
  renderAt("/b/1/brand");
  expect(await screen.findByRole("tab", { name: /^Products 1$/ })).toBeInTheDocument();
});

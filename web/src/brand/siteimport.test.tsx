import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const editor = { id: 2, email: "eli@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const brand = { id: 1, name: "fomo", slug: "fomo", colours: ["#112233"], fonts: ["Inter"], tone_notes: "Punchy", never_say: [], legal_line: "", logo_file_id: null };
// The server marks each found product: new, fills an empty description, or have (already described).
const found = {
  logo_url: "https://fomo.app/logo.png",
  colours: ["#112233", "#ff6600"],
  products: [
    { name: "fomo app", short_description: "Trade with friends", mark: "new" },
    { name: "Gold card", short_description: "A metal card", mark: "fills" },
    { name: "Pro plan", short_description: "More charts", mark: "have" },
  ],
};
const read = (status: string, o: object = {}) => ({ id: 40, url: "https://fomo.app", status, reason: "", found: status === "done" ? found : { logo_url: "", colours: [], products: [] }, have_colours: ["#112233"], ...o });
const base = (me: object = owner, extra: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, me],
  "GET /brands": [200, [brand]],
  "GET /brands/1/site-read/estimate": [200, { credits: 3 }],
  "GET /brands/1/site-read/latest": [404, { detail: "This brand's site hasn't been read yet." }],
  "POST /brands/1/site-read": [201, { id: 40 }],
  "GET /brands/1/site-read/40": [200, read("done")],
  ...extra,
});
/** The Brand page; the owner presses Import from website in its top bar first (v5 F_BrandImport). */
async function open(at = "/b/1/brand") {
  renderApp(at);
  const press = await screen.findByRole("button", { name: "Import from website" }, { timeout: 1500 }).catch(() => null);
  if (press && !screen.queryByRole("region", { name: "Import from website" })) await userEvent.click(press);
}
const section = () => screen.findByRole("region", { name: "Import from website" });
async function readSite(url = "https://fomo.app") {
  await userEvent.type(await screen.findByLabelText("Paste the brand's website"), url);
  await userEvent.click(await screen.findByRole("button", { name: "Read the site · about 3 credits" }));
}
afterEach(() => vi.unstubAllGlobals());

test("the owner pastes the site and reads it for about 3 credits; a bad address says so and nothing runs (flows BR2)", async () => {
  setViewport(1440);
  const calls = fakeServer(base());
  await open();
  await readSite("fomo dot app");
  expect(await screen.findByText("Paste a web address (https://…)")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /brands/1/site-read")).toBe(false);
});

test("while it reads it says so, then the review ticks what's new: the logo (shown from our server), a new colour, a new product and an empty description", async () => {
  setViewport(1440);
  const routes = base(owner, { "GET /brands/1/site-read/40": [200, read("reading")] });
  const calls = fakeServer(routes);
  await open();
  await readSite();
  expect(await screen.findByText("Reading the site…")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /brands/1/site-read")?.body).toEqual({ url: "https://fomo.app" });
  routes["GET /brands/1/site-read/40"] = [200, read("done")];
  const card = await section();
  expect(await within(card).findByRole("checkbox", { name: "Logo found on the site" }, { timeout: 4000 })).toBeChecked();
  expect(within(card).getByAltText("The logo found on the site")).toHaveAttribute("src", "/api/brands/1/site-read/40/logo"); // never the site's own address
  expect(within(card).getByText("Already in your colours")).toBeInTheDocument();
  expect(within(card).getAllByRole("checkbox")).toHaveLength(4); // the logo, #ff6600, fomo app, Gold card: never #112233 or Pro plan
  expect(within(card).getByText("New product")).toBeInTheDocument();
  expect(within(card).getByText("Fills an empty description")).toBeInTheDocument();
  expect(within(card).getByText("Already in your products")).toBeInTheDocument();
  expect(within(card).getByText(/Nothing is saved yet/)).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: "Read it again · about 3 credits" })).toBeInTheDocument();
  expect(card.textContent).not.toMatch(/\$/);
});

test("Save N picked counts the ticks, sends just them, says what it saved, and Undo puts it back", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, {
    "POST /brands/1/site-read/40/save": [200, { colours_added: 1, logo: true, products_made: 1, products_filled: 0, problems: [] }],
    "POST /brands/1/site-read/40/undo": [204, null],
  }));
  await open();
  await readSite();
  const card = await section();
  expect(await screen.findByRole("button", { name: "Save 4 picked" })).toBeEnabled();
  await userEvent.click(await within(card).findByRole("checkbox", { name: /Gold card/ })); // untick
  await userEvent.click(screen.getByRole("button", { name: "Save 3 picked" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands/1/site-read/40/save")?.body).toEqual({ logo: true, colours: ["#ff6600"], products: [0] }));
  expect(await screen.findByText("Saved the logo, 1 colour, 1 product.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/site-read/40/undo")).toBe(true));
});

test("a logo that didn't come says so at Save, and the rest is saved", async () => {
  setViewport(1440);
  fakeServer(base(owner, { "POST /brands/1/site-read/40/save": [200, { colours_added: 1, logo: false, products_made: 2, products_filled: 0, problems: ["Couldn't get the logo from the site."] }] }));
  await open();
  await readSite();
  await userEvent.click(await screen.findByRole("button", { name: /^Save \d+ picked$/ }));
  expect(await screen.findByText("Saved 1 colour, 2 products. Couldn't get the logo from the site.")).toBeInTheDocument();
});

test("a site that couldn't be read says nothing was charged, and keeps the address for Read it again", async () => {
  setViewport(1440);
  fakeServer(base(owner, { "GET /brands/1/site-read/40": [200, read("failed", { reason: "Couldn't read that site. Nothing was charged." })] }));
  await open();
  await readSite();
  expect(await screen.findByText("Couldn't read that site. Nothing was charged.")).toBeInTheDocument();
  expect(screen.getByLabelText("Paste the brand's website")).toHaveValue("https://fomo.app");
  expect(screen.getByRole("button", { name: "Read it again · about 3 credits" })).toBeInTheDocument();
});

test("a page with nothing useful says to try the home page", async () => {
  setViewport(1440);
  fakeServer(base(owner, { "GET /brands/1/site-read/40": [200, read("empty", { reason: "Nothing useful on that page. Try the home page." })] }));
  await open();
  await readSite("https://fomo.app/blog");
  expect(await screen.findByText("Nothing useful on that page. Try the home page.")).toBeInTheDocument();
});

test("unsaved changes to the Look hold Save N picked, and say how to go on", async () => {
  setViewport(1440);
  fakeServer(base(owner, { "GET /brands/1/site-read/latest": [200, read("done")] }));
  renderApp("/b/1/brand");
  await userEvent.type(await screen.findByLabelText(/^Name/), " Co"); // a change on the Look
  await userEvent.click(screen.getByRole("button", { name: "Import from website" }));
  const go = await screen.findByRole("button", { name: "Save 4 picked" });
  expect(go).toBeDisabled();
  expect(go).toHaveAccessibleDescription("Cancel, then save or undo your changes to the Look first");
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(await screen.findByLabelText(/^Name/)).toHaveValue("fomo Co"); // the typing is kept
});

test("an editor doesn't see the section", async () => {
  setViewport(1440);
  fakeServer(base(editor));
  await open();
  await screen.findByLabelText(/^Name/);
  expect(screen.queryByRole("region", { name: "Import from website" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Import from website" })).toBeNull();
});

test("on a phone the review stacks and Cancel and Save sit in the action bar", async () => {
  setViewport(390);
  fakeServer(base());
  await open();
  await readSite();
  const card = await section();
  await within(card).findByRole("checkbox", { name: "Logo found on the site" });
  expect(within(card).queryByRole("button", { name: /picked/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Save 4 picked" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull(); // one Save in the bar
});

test("Import from website reopens on the last read with its address filled; Cancel closes it, and ?import=1 opens it at once", async () => {
  setViewport(1440);
  fakeServer(base(owner, { "GET /brands/1/site-read/latest": [200, read("done")] }));
  await open();
  const card = await section();
  expect(within(card).getByLabelText("Paste the brand's website")).toHaveValue("https://fomo.app");
  expect(await within(card).findByRole("checkbox", { name: "Logo found on the site" })).toBeChecked();
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("region", { name: "Import from website" })).toBeNull();
  cleanup();
  renderApp("/b/1/brand?import=1"); // New brand with a website lands here
  expect(await section()).toBeInTheDocument();
});

test("a read already saved says so, and Read it again is one press", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, { "GET /brands/1/site-read/latest": [200, read("saved")] }));
  await open();
  expect(await screen.findByText("The last read is saved. Read it again to see what's on the site now.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Read it again · about 3 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands/1/site-read")?.body).toEqual({ url: "https://fomo.app" }));
});

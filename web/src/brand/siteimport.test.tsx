import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const editor = { id: 2, email: "eli@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const brand = { id: 1, name: "fomo", slug: "fomo", colours: ["#112233"], fonts: ["Inter"], tone_notes: "Punchy", never_say: [], legal_line: "", logo_file_id: null };
const found = {
  logo_url: "https://fomo.app/logo.png",
  colours: ["#112233", "#ff6600"],
  products: [
    { name: "fomo app", short_description: "Trade with friends" },
    { name: "Gold card", short_description: "A metal card" },
    { name: "Pro plan", short_description: "More charts" },
  ],
};
const props = [
  { id: 7, kind: "prop", name: "Gold Card", short_description: "", brand_ids: [1] }, // fills its empty description
  { id: 8, kind: "prop", name: "Pro plan", short_description: "Already said", brand_ids: [1] }, // nothing to do
];
const read = (status: string, o: object = {}) => ({ status, reason: "", found: status === "done" ? found : { logo_url: "", colours: [], products: [] }, have_colours: ["#112233"], ...o });
const base = (me: object = owner, extra: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, me],
  "GET /brands": [200, [brand]],
  "GET /brands/1/site-read/estimate": [200, { credits: 3 }],
  "GET /library/prop": [200, props],
  "POST /brands/1/site-read": [201, { id: 40 }],
  "GET /brands/1/site-read/40": [200, read("done")],
  ...extra,
});
function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/brand"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
const section = () => screen.findByRole("heading", { name: "Import from website" }).then((h) => h.closest("div.rounded-lg") as HTMLElement);
async function readSite(url = "https://fomo.app") {
  await userEvent.type(await screen.findByLabelText("Paste the brand's website"), url);
  await userEvent.click(await screen.findByRole("button", { name: "Read the site · about 3 credits" }));
}
afterEach(() => vi.unstubAllGlobals());

test("the owner pastes the site and reads it for about 3 credits; a bad address says so and nothing runs (flows BR2)", async () => {
  setViewport(1440);
  const calls = fakeServer(base());
  open();
  await readSite("fomo dot app");
  expect(await screen.findByText("Paste a web address (https://…)")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /brands/1/site-read")).toBe(false);
});

test("while it reads it says so, then the review ticks what's new: the logo, a new colour, a new product and an empty description", async () => {
  setViewport(1440);
  const routes = base(owner, { "GET /brands/1/site-read/40": [200, read("reading")] });
  const calls = fakeServer(routes);
  open();
  await readSite();
  expect(await screen.findByText("Reading the site…")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /brands/1/site-read")?.body).toEqual({ url: "https://fomo.app" });
  routes["GET /brands/1/site-read/40"] = [200, read("done")];
  const card = await section();
  expect(await within(card).findByRole("checkbox", { name: "The logo on the site" }, { timeout: 4000 })).toBeChecked();
  expect(within(card).getByText("Already in your colours")).toBeInTheDocument();
  expect(within(card).getAllByRole("checkbox")).toHaveLength(4); // the logo, #ff6600, fomo app, Gold card: never #112233 or Pro plan
  expect(within(card).getByText("New product")).toBeInTheDocument();
  expect(within(card).getByText("Fills an empty description")).toBeInTheDocument();
  expect(within(card).getByText("Already in your products")).toBeInTheDocument();
  expect(within(card).getByText(/Nothing is saved yet/)).toBeInTheDocument();
  expect(card.textContent).not.toMatch(/\$/);
});

test("Save the ticked ones sends just the ticks, says what it saved, and Undo puts it back", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, {
    "POST /brands/1/site-read/40/save": [200, { colours_added: 1, logo: true, products_made: 1, products_filled: 0, problems: [] }],
    "POST /brands/1/site-read/40/undo": [204, null],
  }));
  open();
  await readSite();
  const card = await section();
  await userEvent.click(await within(card).findByRole("checkbox", { name: /Gold card/ })); // untick
  await userEvent.click(within(card).getByRole("button", { name: "Save the ticked ones" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands/1/site-read/40/save")?.body).toEqual({ logo: true, colours: ["#ff6600"], products: [0] }));
  expect(await screen.findByText("Saved the logo, 1 colour, 1 product.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/site-read/40/undo")).toBe(true));
});

test("a logo that didn't come says so at Save, and the rest is saved", async () => {
  setViewport(1440);
  fakeServer(base(owner, { "POST /brands/1/site-read/40/save": [200, { colours_added: 1, logo: false, products_made: 2, products_filled: 0, problems: ["Couldn't get the logo from the site."] }] }));
  open();
  await readSite();
  await userEvent.click(await within(await section()).findByRole("button", { name: "Save the ticked ones" }));
  expect(await screen.findByText("Saved 1 colour, 2 products. Couldn't get the logo from the site.")).toBeInTheDocument();
});

test("a site that couldn't be read says nothing was charged, and Try again goes back to the box", async () => {
  setViewport(1440);
  fakeServer(base(owner, { "GET /brands/1/site-read/40": [200, read("failed", { reason: "Couldn't read that site. Nothing was charged." })] }));
  open();
  await readSite();
  expect(await screen.findByText("Couldn't read that site. Nothing was charged.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(screen.getByLabelText("Paste the brand's website")).toHaveValue("https://fomo.app");
});

test("a page with nothing useful says to try the home page", async () => {
  setViewport(1440);
  fakeServer(base(owner, { "GET /brands/1/site-read/40": [200, read("empty", { reason: "Nothing useful on that page. Try the home page." })] }));
  open();
  await readSite("https://fomo.app/blog");
  expect(await screen.findByText("Nothing useful on that page. Try the home page.")).toBeInTheDocument();
});

test("unsaved changes in the form below hold Save the ticked ones", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  await readSite();
  const card = await section();
  await within(card).findByRole("button", { name: "Save the ticked ones" });
  await userEvent.clear(screen.getByLabelText("How we sound"));
  await userEvent.type(screen.getByLabelText("How we sound"), "Calm");
  const go = within(card).getByRole("button", { name: "Save the ticked ones" });
  expect(go).toBeDisabled();
  expect(go).toHaveAccessibleDescription("Save or undo your changes below first");
});

test("an editor doesn't see the section", async () => {
  setViewport(1440);
  fakeServer(base(editor));
  open();
  await screen.findByLabelText("How we sound");
  expect(screen.queryByRole("heading", { name: "Import from website" })).toBeNull();
});

test("on a phone the review stacks and Save sits in the action bar", async () => {
  setViewport(390);
  fakeServer(base());
  open();
  await readSite();
  const card = await section();
  await within(card).findByRole("checkbox", { name: "The logo on the site" });
  expect(within(card).queryByRole("button", { name: "Save the ticked ones" })).toBeNull();
  expect(screen.getByRole("button", { name: "Save the ticked ones" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull(); // one press in the bar while the form is untouched
});

test("a logo picture that won't load here is named instead", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  await readSite();
  const card = await section();
  fireEvent.error(await within(card).findByRole("img", { name: "The logo on the site" }));
  expect(within(card).getByRole("checkbox", { name: "The logo on the site (logo.png)" })).toBeChecked();
});

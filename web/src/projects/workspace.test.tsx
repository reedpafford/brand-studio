import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "Show the buy flow", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 60, credits_used: 0, budget_pct: 0,
};
const script = { version: 4, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Mia scrolls her phone." };
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /credits/rates": [200, []],
  "GET /jobs": [200, []],
  "GET /projects/9/script/suggestions": [200, []],
  "GET /projects/9/script/notes": [200, []],
};

function open(query = "") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/projects/9${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

/** The page's Script button (the one that opens the panel), not the Script step in the step list. */
const scriptButton = () => screen.getByRole("button", { name: "Show script" });

test("a video has a header with the credits, six steps with ticks, and one Next button", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open();
  expect(await screen.findByRole("heading", { name: /Mia buys the dip/ })).toBeInTheDocument();
  expect(within(screen.getByRole("main")).getByRole("link", { name: "Videos" })).toHaveAttribute("href", "/b/1/videos");
  expect(screen.getByText(/0 \/ 60 credits/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Brief" })).toBeInTheDocument();
  expect(screen.getByText("Show the buy flow")).toBeInTheDocument();
  const steps = screen.getByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button")).toHaveLength(6);
  for (const name of ["Brief", "Script", "Shots", "Storyboard", "Clips", "Final video"]) expect(within(steps).getByRole("button", { name })).toBeInTheDocument();
  expect(within(steps).getByRole("button", { name: "Brief" })).toHaveAttribute("aria-current", "step");
  expect(screen.getByRole("button", { name: "Next: Script" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Next: Script" }));
  expect(await screen.findByRole("heading", { name: "Script" })).toBeInTheDocument();
  expect(screen.getByText("Mia scrolls her phone.")).toBeInTheDocument();
});

test("steps after the one you can reach are locked and say why; reachable ones can be opened", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=script");
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getByRole("button", { name: "Script" })).toHaveAttribute("aria-current", "step");
  expect(within(steps).getByRole("button", { name: "Shots" })).not.toHaveAttribute("aria-disabled", "true");
  const storyboard = within(steps).getByRole("button", { name: "Storyboard" });
  expect(storyboard).toHaveAttribute("aria-disabled", "true");
  expect(storyboard).toHaveAccessibleDescription("Make the shots first");
  expect(within(steps).getByRole("button", { name: "Final video" })).toHaveAttribute("aria-disabled", "true");
  await userEvent.click(storyboard);
  expect(screen.getByRole("heading", { name: "Script" })).toBeInTheDocument(); // still here
});

test("without a script Next is disabled and says why, and the later steps are locked", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/script": [404, { detail: "This project has no script yet." }] });
  open("?stage=script");
  const next = await screen.findByRole("button", { name: "Next: Shots" });
  expect(next).toBeDisabled();
  expect(next).toHaveAccessibleDescription("Finish Script first");
});

test("the old Enhance and Breakdown addresses open Script and Shots", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=enhance");
  expect(await screen.findByRole("heading", { name: "Script" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Suggest directions/ })).toBeInTheDocument(); // Enhance now lives inside Script
});

test("a link to a locked step lands on the first unfinished one", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=storyboard");
  expect(await screen.findByRole("heading", { name: "Shots" })).toBeInTheDocument();
});

test("from Shots on the script is a button: a side panel on desktop, read only, with Edit in Script", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=shots");
  await screen.findByRole("heading", { name: "Shots" });
  await userEvent.click(scriptButton());
  const panel = await screen.findByRole("dialog", { name: "Script" });
  expect(within(panel).getByText("Mia scrolls her phone.")).toBeInTheDocument();
  await userEvent.click(within(panel).getByRole("button", { name: "Edit in Script" }));
  expect(await screen.findByRole("heading", { name: "Script" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("the Script button is not on Brief or Script, where the script is the page", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=script");
  await screen.findByRole("heading", { name: "Script" });
  expect(screen.queryByRole("button", { name: "Show script" })).not.toBeInTheDocument();
});

test("on a phone one step button opens a sheet of the six steps; there are no Script / step tabs", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=script");
  const picker = await screen.findByRole("button", { name: /Step 2 of 6 · Script/ });
  expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  await userEvent.click(picker);
  const sheet = screen.getByRole("dialog", { name: "Steps" });
  expect(within(sheet).getAllByRole("button")).toHaveLength(7); // six steps and the sheet's close button
  expect(within(sheet).getAllByText("Make the shots first").length).toBeGreaterThan(0);
  await userEvent.click(within(sheet).getByRole("button", { name: "Shots" }));
  expect(await screen.findByRole("heading", { name: "Shots" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog", { name: "Steps" })).not.toBeInTheDocument();
});

test("on a phone Next sits in the action bar above the tabs, and Script is an icon button", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=shots");
  const next = await screen.findByRole("button", { name: /Next: Storyboard/ });
  expect(next).toBeDisabled();
  expect(scriptButton()).toBeDefined();
});

test("a video can be renamed", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /projects/9/script": [200, script], "PATCH /projects/9": [200, project] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Rename" }));
  const name = screen.getByLabelText("Name");
  await userEvent.clear(name);
  await userEvent.type(name, "Mia sells the top");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /projects/9")?.body).toEqual({ name: "Mia sells the top" }));
});

const bag = (id: number, variant: string) => ({ id, brand_id: 1, name: `${variant} bag`, tags: [], default_for: [], product: "bag", variant, file_id: id });
const briefRoutes = {
  ...base,
  "GET /projects/9": [200, { ...project, cast_ids: [4], product_variants: { bag: "Chicken" } }] as [number, unknown],
  "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [], sheet_status: "approved" }, { id: 5, name: "Dex", image_file_ids: [], sheet_status: "approved" }]] as [number, unknown],
  "GET /brands/1/screens": [200, [bag(1, "Chicken"), bag(2, "Peanut butter")]] as [number, unknown],
};

test("the brief shows who is in it and which flavour, and can be edited after the project is made", async () => {
  const calls = fakeServer({ ...briefRoutes, "PATCH /projects/9": [200, project] });
  open();
  expect(await screen.findByText("In it: Mia")).toBeInTheDocument();
  expect(screen.getByText("Bag: Chicken")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit brief" }));
  // While editing, Save brief is the only amber button: Next is hidden.
  expect(screen.queryByRole("button", { name: /Next: Script/ })).not.toBeInTheDocument();
  expect(screen.queryByText(/doesn't rewrite the script/)).not.toBeInTheDocument(); // no script yet
  await userEvent.click(await screen.findByRole("button", { name: "Peanut butter" }));
  await userEvent.click(screen.getByLabelText("Dex"));
  const length = screen.getByLabelText(/Planned length/);
  await userEvent.clear(length);
  await userEvent.type(length, "45");
  await userEvent.click(screen.getByRole("button", { name: "Save brief" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /projects/9")?.body).toMatchObject({ cast_ids: [4, 5], planned_seconds: 45, product_variants: { bag: "Peanut butter" }, goal: "Show the buy flow" }));
});

test("a refused brief edit shows the server's reason and Cancel leaves it as it was", async () => {
  fakeServer({ ...briefRoutes, "PATCH /projects/9": [422, { detail: "Plan 90 seconds or less." }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit brief" }));
  await userEvent.click(screen.getByRole("button", { name: "Save brief" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Plan 90 seconds or less.");
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByText("In it: Mia")).toBeInTheDocument();
});

test("editing the brief after a script exists says saving does not rewrite the script, and Next is 44px on phones", async () => {
  fakeServer({ ...briefRoutes, "GET /projects/9/script": [200, script] });
  open();
  const next = await screen.findByRole("button", { name: "Next: Script" });
  expect(next.className).toContain("min-h-control");
  await userEvent.click(screen.getByRole("button", { name: "Edit brief" }));
  expect(screen.getByText("Saving doesn't rewrite the script or the steps after it. Redo them if the change matters.")).toBeInTheDocument();
});

const reel = { id: "fomo-DehudnaAmce", name: "Altar rejection", logline: "A groom is rejected.", seconds: 45, style: "3D", brand: "fomo", has_thumbnail: true };

test("the brief says which reel is being adapted, and the reel can be changed or removed", async () => {
  const withReel = { ...project, cast_ids: [4], product_variants: { bag: "Chicken" }, reference_breakdown: { source_id: "fomo-DehudnaAmce" }, reference_replace: "Make the montage about trading." };
  const calls = fakeServer({ ...briefRoutes, "GET /projects/9": [200, withReel], "GET /references": [200, [reel]], "PATCH /projects/9": [200, project] });
  open();
  expect(await screen.findByText(/Adapting: Altar rejection/)).toBeInTheDocument();
  expect(screen.getByText("Replace: Make the montage about trading.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit brief" }));
  await userEvent.click(await screen.findByRole("button", { name: /Altar rejection/ })); // tapping the picked reel again removes it
  await userEvent.click(screen.getByRole("button", { name: "Save brief" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /projects/9")?.body).toMatchObject({ reference_breakdown: null, reference_replace: "" }));
});

test("picking a reel in the brief editor sends reference_id and what to replace", async () => {
  const calls = fakeServer({ ...briefRoutes, "GET /references": [200, [reel]], "PATCH /projects/9": [200, project] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit brief" }));
  await userEvent.click(await screen.findByRole("button", { name: /Altar rejection/ }));
  await userEvent.type(screen.getByLabelText(/What to replace/), "Swap the montage.");
  await userEvent.click(screen.getByRole("button", { name: "Save brief" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /projects/9")?.body).toMatchObject({ reference_id: "fomo-DehudnaAmce", reference_replace: "Swap the montage." }));
});

test("Cancel throws the edits away: the next Edit brief starts from what is saved", async () => {
  fakeServer({ ...briefRoutes });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit brief" }));
  const goal = screen.getByLabelText("What's it for?");
  await userEvent.clear(goal);
  await userEvent.type(goal, "Something else");
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await userEvent.click(screen.getByRole("button", { name: "Edit brief" }));
  expect(screen.getByLabelText("What's it for?")).toHaveValue("Show the buy flow");
});

test("the brief editor's length field has the same cap as the new-video page, from the server", async () => {
  fakeServer({ ...briefRoutes, "GET /credits/limits": [200, { max_planned_seconds: 60, weekly_quick_clip_credits: 150, per_video_max_credits: 340 }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit brief" }));
  const length = screen.getByLabelText(/Planned length/);
  await vi.waitFor(() => expect(length).toHaveAttribute("max", "170"));
});

test("on a phone the video's own line replaces the brand bar: back, name, percent used, and the Next button fills the bar", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=script");
  expect(await screen.findByRole("heading", { level: 1, name: "Mia buys the dip" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Brand: / })).not.toBeInTheDocument();
  expect(within(screen.getByRole("main")).getByRole("link", { name: "Videos" })).toHaveAttribute("href", "/b/1/videos");
  expect(screen.getByText(/of the budget used/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Shots" }).closest("div")).toHaveClass("[&_button]:w-full");
});

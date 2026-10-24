import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

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

test("the script stays on the left while the stage changes on the right", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open();
  expect(await screen.findByText("Mia scrolls her phone.")).toBeInTheDocument();
  expect(screen.getByLabelText("Brief")).toHaveTextContent("Show the buy flow");
  const steps = screen.getByRole("list", { name: "Stages" });
  await userEvent.click(within(steps).getByRole("button", { name: /Enhance/ }));
  expect(await screen.findByLabelText("Enhance stage")).toHaveTextContent("It never changes your words");
  expect(screen.getByText("Mia scrolls her phone.")).toBeInTheDocument();
});

test("done steps get a tick, and locked steps cannot be opened and say why", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=enhance");
  const steps = await screen.findByRole("list", { name: "Stages" });
  expect(within(steps).getByRole("button", { name: /✓ Brief/ })).toBeInTheDocument();
  expect(within(steps).getByRole("button", { name: /✓ Script/ })).toBeInTheDocument();
  expect(within(steps).getByRole("button", { name: /Enhance/ })).toHaveAttribute("aria-current", "step");
  const clips = within(steps).getByRole("button", { name: "Clips" });
  expect(clips).toBeDisabled();
  expect(clips).toHaveAttribute("title", "Fix the breakdown first");
});

test("without a script the next step waits for one", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [404, { detail: "This project has no script yet." }] });
  open("?stage=script");
  expect(await screen.findByText("Finish the script first.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Enhance →" })).toBeDisabled();
});

test("on a phone a Stage menu replaces the steps, and Script / stage tabs switch panes", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open();
  const menu = await screen.findByLabelText("Stage");
  expect(within(menu).getByRole("option", { name: "Clips (fix the breakdown first)" })).toBeDisabled();
  await userEvent.selectOptions(menu, "Enhance");
  expect(await screen.findByLabelText("Enhance stage")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Enhance" })).toBeInTheDocument();
});

test("Enhance stays locked until a script exists, and a link to it lands on the Script step", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [404, { detail: "This project has no script yet." }] });
  open("?stage=enhance");
  expect(await screen.findByLabelText("Script stage")).toBeInTheDocument();
  const steps = screen.getByRole("list", { name: "Stages" });
  const enhance = within(steps).getByRole("button", { name: /Enhance/ });
  expect(enhance).toBeDisabled();
  expect(enhance).toHaveAttribute("title", "Finish the script first");
  expect(within(screen.getByLabelText("Stage")).getByRole("option", { name: "Enhance (finish the script first)" })).toBeDisabled();
});

test("a link to a stage that isn't open yet lands on the first unfinished one", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=storyboard");
  expect(await screen.findByLabelText("Breakdown")).toBeInTheDocument();
});

test("the guidance points at the script pane, not 'the left', so it reads right on a phone", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=script");
  expect(await screen.findByLabelText("Script stage")).toHaveTextContent("in the script pane");
  expect(document.body.textContent).not.toMatch(/on the left/);
});

test("choosing a stage on a phone shows that stage, not the script tab", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=script");
  const tabs = await screen.findByRole("tablist");
  await userEvent.click(within(tabs).getAllByRole("tab")[0]);
  expect(within(tabs).getAllByRole("tab")[0]).toHaveAttribute("aria-selected", "true");
  const steps = await screen.findByRole("list", { name: "Stages" });
  await userEvent.click(within(steps).getByRole("button", { name: /Enhance/ }));
  expect(within(tabs).getAllByRole("tab")[1]).toHaveAttribute("aria-selected", "true");
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
  // While editing, Save brief is the only primary: Next is hidden.
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
  const next = await screen.findByRole("button", { name: "Next: Script →" });
  expect(next.className).toContain("min-h-11");
  await userEvent.click(screen.getByRole("button", { name: "Edit brief" }));
  expect(screen.getByText("Saving doesn't rewrite the script or the steps after it. Redo them if the change matters.")).toBeInTheDocument();
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

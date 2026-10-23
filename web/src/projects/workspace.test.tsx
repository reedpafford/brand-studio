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

test("done steps get a tick, and steps not built yet cannot be opened and say why", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [200, script] });
  open("?stage=enhance");
  const steps = await screen.findByRole("list", { name: "Stages" });
  expect(within(steps).getByRole("button", { name: /✓ Brief/ })).toBeInTheDocument();
  expect(within(steps).getByRole("button", { name: /✓ Script/ })).toBeInTheDocument();
  expect(within(steps).getByRole("button", { name: /Enhance/ })).toHaveAttribute("aria-current", "step");
  const breakdown = within(steps).getByRole("button", { name: "Breakdown" });
  expect(breakdown).toBeDisabled();
  expect(breakdown).toHaveAttribute("title", "Coming soon");
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
  expect(within(menu).getByRole("option", { name: "Breakdown (coming soon)" })).toBeDisabled();
  await userEvent.selectOptions(menu, "Enhance");
  expect(await screen.findByLabelText("Enhance stage")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Enhance" })).toBeInTheDocument();
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const brands = [{ id: 1, name: "fomo", colours: [] }];
const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "Show the buy flow", platform: "TikTok",
  aspect_ratio: "9:16", format: "Story", cast_ids: [4], reference_file_id: null, estimate_credits: 30, budget_credits: 660, credits_used: 412, budget_pct: 62.4,
};
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, brands],
  "GET /credits/limits": [200, { weekly_quick_clip_credits: 150, per_video_max_credits: 340 }],
  "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [], sheet_status: "approved" }]],
};

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

test("the list shows each video with its credits, says when it is nearly or over budget, and flags one waiting for approval", async () => {
  fakeServer({ ...base, "GET /projects": [200, [project, { ...project, id: 10, name: "Long one", status: "needs_owner_approval", budget_pct: 110 }]] });
  renderAt("/b/1/projects");
  expect(await screen.findByText("Mia buys the dip")).toBeInTheDocument();
  expect(screen.getByText("412 / 660 credits · 62%")).toBeInTheDocument();
  expect(screen.getByText(/110% · Over budget/)).toBeInTheDocument();
  expect(screen.getByText("Waiting for Reed to approve")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$/);
});

test("an empty brand invites a first video", async () => {
  fakeServer({ ...base, "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  expect(await screen.findByText("No videos for fomo yet.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "New video" })).toHaveAttribute("href", "/b/1/projects/new");
});

test("the brief is sent with the cast and shape, then you land on the project", async () => {
  const calls = fakeServer({ ...base, "POST /projects": [201, project], "GET /projects/9": [200, project], "GET /projects": [200, []] });
  renderAt("/b/1/projects/new");
  await userEvent.type(await screen.findByLabelText("Title"), "Mia buys the dip");
  await userEvent.type(screen.getByLabelText("What's it for?"), "Show the buy flow");
  await userEvent.click(screen.getByRole("button", { name: "1:1" }));
  await userEvent.click(await screen.findByLabelText("Mia"));
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));
  expect(await screen.findByRole("heading", { name: "Mia buys the dip" })).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /projects")?.body).toMatchObject({
    brand_id: 1, name: "Mia buys the dip", goal: "Show the buy flow", platform: "TikTok", aspect_ratio: "1:1", planned_seconds: 30, cast_ids: [4], reference_file_id: null,
  });
  expect(screen.getByText("412 / 660 credits · 62%")).toBeInTheDocument();
});

test("the longest length comes from the server's per-video cap; there is no editor length limit", async () => {
  fakeServer({ ...base });
  renderAt("/b/1/projects/new");
  const length = await screen.findByLabelText(/Planned length/);
  await waitFor(() => expect(length).toHaveAttribute("max", "170")); // 340 / 2, from the server
  expect(screen.getByText(/Budget: 60 credits/)).toBeInTheDocument();
  await userEvent.clear(length);
  await userEvent.type(length, "90");
  expect(screen.queryByText(/has to approve/)).not.toBeInTheDocument();
});

test("a refused brief shows the server's reason", async () => {
  fakeServer({ ...base, "POST /projects": [422, { detail: "Plan 170 seconds or less." }] });
  renderAt("/b/1/projects/new");
  await userEvent.type(await screen.findByLabelText("Title"), "Too long");
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Plan 170 seconds or less.");
});

test("the meter says 'Almost at budget' from 75% and has a bar", async () => {
  fakeServer({ ...base, "GET /projects": [200, [{ ...project, budget_pct: 81, credits_used: 620, budget_credits: 765 }]] });
  renderAt("/b/1/projects");
  expect(await screen.findByText("620 / 765 credits · 81% · Almost at budget")).toBeInTheDocument();
});

import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
  aspect_ratio: "9:16", format: "Story", cast_ids: [4], reference_file_id: null, estimate_credits: 30, budget_credits: 660, credits_used: 412, budget_pct: 62.4, created_by_id: 2,
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

/** The earlier videos live on Scripts, under "Videos made before scripts" (the old list redirects to Videos). */
async function openLegacy(n: number) {
  renderAt("/b/1/scripts");
  await userEvent.click(await screen.findByText(`Videos made before scripts (${n})`));
}
const scripts: Record<string, [number, unknown]> = { "GET /scripts": [200, []], "GET /references": [200, []], "GET /jobs": [200, []] };

test("the list shows each video with its credits, says when it is nearly or over budget, and marks one held from before as waiting for the owner", async () => {
  fakeServer({ ...base, ...scripts, "GET /projects": [200, [project, { ...project, id: 10, name: "Long one", status: "needs_owner_approval", budget_pct: 110 }]] });
  await openLegacy(2);
  expect(await screen.findByText("Mia buys the dip")).toBeInTheDocument();
  expect(screen.getByText("412 of 660 credits")).toBeInTheDocument();
  expect(screen.getByText(/Over budget/)).toBeInTheDocument();
  expect(screen.getByText("Waiting for the owner's OK")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$/);
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
  expect(screen.queryByText(/Reed has to approve/)).not.toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/Up to \d+s/);
});

test("a refused brief shows the server's reason", async () => {
  fakeServer({ ...base, "POST /projects": [422, { detail: "Plan 170 seconds or less." }] });
  renderAt("/b/1/projects/new");
  await userEvent.type(await screen.findByLabelText("Title"), "Too long");
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Plan 170 seconds or less.");
});

test("the meter says 'Almost at budget' from 75% and has a bar", async () => {
  fakeServer({ ...base, ...scripts, "GET /projects": [200, [{ ...project, budget_pct: 81, credits_used: 620, budget_credits: 765 }]] });
  await openLegacy(1);
  expect(await screen.findByText("620 of 765 credits · Almost at budget")).toBeInTheDocument();
});

test("a product with one flavour is picked for you", async () => {
  const calls = fakeServer({
    ...base,
    "GET /brands/1/screens": [200, [{ id: 1, brand_id: 1, name: "Chicken bag", tags: [], default_for: [], product: "bag", variant: "Chicken", file_id: 1 }]],
    "POST /projects": [201, project],
    "GET /projects/9": [200, project],
    "GET /projects": [200, []],
  });
  renderAt("/b/1/projects/new");
  await userEvent.type(await screen.findByLabelText("Title"), "Dinner");
  expect(await screen.findByRole("button", { name: "Chicken" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects")?.body).toMatchObject({ product_variants: { bag: "Chicken" } }));
});

const reels = [
  { id: "fomo-DehudnaAmce", name: "Altar rejection", logline: "A groom is rejected at the altar and turns it into a win.", seconds: 45, style: "3D animated", brand: "fomo", has_thumbnail: true },
  { id: "other", name: "Other reel", logline: "Something else.", seconds: 20, style: "live", brand: "", has_thumbnail: false },
];

test("a reference reel can be picked on the brief, with what to replace, and nothing is picked by default", async () => {
  const calls = fakeServer({ ...base, "GET /references": [200, reels], "POST /projects": [201, project], "GET /projects/9": [200, project], "GET /projects": [200, []] });
  renderAt("/b/1/projects/new");
  await userEvent.type(await screen.findByLabelText("Title"), "Altar reel");
  expect(await screen.findByText("Adapt a reference reel (optional)")).toBeInTheDocument();
  expect(screen.queryByLabelText(/What to replace/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Altar rejection/ })).toHaveAttribute("aria-pressed", "false");
  await userEvent.click(screen.getByRole("button", { name: /Altar rejection/ }));
  await userEvent.type(screen.getByLabelText(/What to replace/), "The reselling montage becomes a fomo trading montage.");
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects")?.body).toMatchObject({ reference_id: "fomo-DehudnaAmce", reference_replace: "The reselling montage becomes a fomo trading montage." }));
});

test("without a pick, no reference is sent", async () => {
  const calls = fakeServer({ ...base, "GET /references": [200, reels], "POST /projects": [201, project], "GET /projects/9": [200, project], "GET /projects": [200, []] });
  renderAt("/b/1/projects/new");
  await userEvent.type(await screen.findByLabelText("Title"), "Plain");
  await screen.findByText("Adapt a reference reel (optional)");
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects")).toBe(true));
  expect(calls.find((c) => c.key === "POST /projects")?.body).not.toHaveProperty("reference_id");
});

test("the upload is called Your own example video and says how it is used, so it is not confused with the reference reels", async () => {
  fakeServer({ ...base, "GET /references": [200, reels] });
  renderAt("/b/1/projects/new");
  expect(await screen.findByText("Adapt a reference reel (optional)")).toBeInTheDocument();
  expect(screen.getByText("Your own example video (optional)")).toBeInTheDocument();
  expect(screen.getByText(/Claude does not watch it yet/)).toBeInTheDocument();
  expect(screen.queryByText("Reference video (optional)")).not.toBeInTheDocument();
});

test("an earlier video's card is one link to its page and says the step it is at; the old list lands on Videos", async () => {
  fakeServer({ ...base, ...scripts, "GET /projects": [200, [project]] });
  await openLegacy(1);
  expect(await screen.findByRole("link", { name: "Mia buys the dip, Brief, Brief written" })).toHaveAttribute("href", "/b/1/projects/9");
  expect(screen.getByRole("link", { name: "New video (the earlier way)" })).toHaveAttribute("href", "/b/1/projects/new");
  cleanup();
  vi.unstubAllGlobals();
  fakeServer({ ...base, ...scripts, "GET /projects": [200, [project]] });
  renderAt("/b/1/projects");
  expect(await screen.findByRole("heading", { name: "Videos", level: 1 })).toBeInTheDocument();
});

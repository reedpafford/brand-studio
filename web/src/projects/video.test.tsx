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
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, product_variants: {},
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Bo eats." };
const breakdown = { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } };
const asset = (o: object) => ({ kind: "character", ref: "char:5", role: "Bo", library_item_id: 5, name: "Bo", locked: false, sheet_status: "needs_approval", ready: false, ...o });
const item = (o: object) => ({ id: 5, kind: "character", name: "Bo", version: 1, sheet_file_id: 70, sheet_status: "needs_approval", ...o });
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /projects/9/breakdown": [200, breakdown],
  "GET /projects/9/storyboard": [200, []],
  "GET /projects/9/clips": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /projects/9/assets": [200, [asset({})]],
  "GET /library/character/5": [200, item({})],
  "GET /library/character": [200, []],
  "GET /brands/1/screens": [200, []],
  "GET /credits/rates": [200, []],
  "GET /jobs": [200, []],
};

function open(query = "?step=assets") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/videos/9${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("the five steps, and Storyboard waits until every asset is approved", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d/, ""))).toEqual(["Breakdown", "Assets", "Storyboard", "Clips", "Downloads"]);
  expect(within(steps).getByRole("button", { name: "Storyboard" })).toHaveAccessibleDescription(/Approve every asset first \(1 left\)/);
  expect(screen.getByRole("button", { name: /Next: Storyboard/ })).toBeDisabled();
});

test("approving an asset opens the next step, and the toast can undo it", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "POST /library/character/5/sheet/approve": [200, item({ sheet_status: "approved" })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character/5/sheet/approve")).toBe(true));
  expect(await screen.findByText("Bo approved.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
});

test("a locked role is already approved and has no buttons", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [asset({ locked: true, sheet_status: "approved", ready: true })]] });
  open();
  const card = await screen.findByLabelText("Bo");
  expect(within(card).getByText("Locked by Reed")).toBeInTheDocument();
  expect(within(card).queryByRole("button")).toBeNull();
});

test("a role with no character picks one from the library", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [asset({ ref: "slot:3", library_item_id: null, name: "", role: "Coach", sheet_status: "missing" })]],
    "GET /library/character": [200, [item({ id: 8, name: "Dana", sheet_status: "approved" })]],
    "PUT /projects/9/assets/slots/3": [200, []],
  });
  open();
  await userEvent.selectOptions(await screen.findByLabelText("Use a Cast & places character"), "8");
  await userEvent.click(screen.getByRole("button", { name: "Use this character" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/assets/slots/3")).toBe(true));
});

const frame = { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], kept: [], file_id: 40, approved: true, stale: false };
const clip = (o: object) => ({ id: 3, clip_id: "c1", seconds: 8, prompt: "Bo sniffs the salmon", references: [], problems: [], kept: [], file_id: null, takes: [], picked_take_id: null, approved: false, stale: false, take_credits: 24, inserts: [], ...o });
const toClips = { ...base, "GET /projects/9/assets": [200, []] as [number, unknown], "GET /projects/9/storyboard": [200, [frame]] as [number, unknown] };

test("a clip's prompt is read and marked Looks good before its take can be made", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({})]] });
  open("?step=clips");
  expect(await screen.findByText("Bo sniffs the salmon")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Make clip/ })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Prompt for c1 looks good" }));
  expect(screen.getByRole("button", { name: /^Make clip/ })).toBeEnabled();
  // The prompt stays, marked, and can be taken back.
  expect(screen.getByText("Looks good")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Prompt for c1 undo looks good" }));
  expect(screen.getByRole("button", { name: /^Make clip/ })).toBeDisabled();
});

test("a prompt shows pictures by name, never [Image1]", async () => {
  setViewport(1440);
  const references = [{ kind: "image", id: "frame:c1", role: "storyboard frame" }, { kind: "image", id: "char:5", role: "Bo's look" }];
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt: "[Image1] is the first frame. [Image2] eats.", references })]] });
  open("?step=clips");
  const prompt = await screen.findByLabelText("Prompt for clip c1");
  expect(prompt).toHaveTextContent("First frame is the first frame. Bo's look eats.");
  expect(prompt).not.toHaveTextContent("[Image");
});

test("advice on a clip can be kept anyway; kept advice says so", async () => {
  setViewport(1440);
  const advice = "Advice: the hook is slow";
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ problems: [advice] }), clip({ id: 4, clip_id: "c2", problems: [advice], kept: [advice] })]], "POST /projects/9/clips/3/keep": [200, clip({})] });
  open("?step=clips");
  await userEvent.click(await screen.findByRole("button", { name: `Keep it anyway: ${advice}` }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/3/keep")?.body).toEqual({ problem: advice }));
  expect(screen.getByText("Kept · Reed will see it")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /Keep it anyway/ })).toHaveLength(1);
});

test("a role with no character can make one, so Assets is never a dead end", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [asset({ ref: "slot:3", library_item_id: null, name: "", role: "Coach", sheet_status: "missing" })]],
    "POST /library/character": [201, item({ id: 12, name: "Coach" })],
    "PUT /projects/9/assets/slots/3": [200, []],
  });
  open();
  expect(screen.queryByLabelText("Use a Cast & places character")).toBeNull();
  await userEvent.click(await screen.findByRole("button", { name: "Make a look" }));
  await vi.waitFor(() => expect(calls.map((c) => c.key)).toEqual(expect.arrayContaining(["POST /library/character", "PUT /projects/9/assets/slots/3"])));
  expect(calls.find((c) => c.key === "POST /library/character")?.body).toMatchObject({ name: "Coach", brand_ids: [1] });
});

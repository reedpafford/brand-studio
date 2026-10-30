import { screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { renderApp } from "../test/render";
import { editor } from "../test/people";

const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 100, credits_used: 70, budget_pct: 70,
};
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [404, { detail: "none" }],
  "GET /projects/9/breakdown": [404, { detail: "none" }],
  "GET /projects/9/storyboard": [200, []],
  "GET /jobs": [200, []],
};
const estimate = {
  stages: [
    { stage: "script", done: true, credits: 0, note: "" },
    { stage: "breakdown", done: false, credits: 6, note: "One Claude call" },
    { stage: "clips", done: false, credits: 40, note: "30 s at 480p, 1 credit a second" },
    { stage: "video", done: false, credits: 0, note: "Putting the clips together costs nothing" },
  ],
  remaining_credits: 46,
  used_credits: 70,
  budget_credits: 100,
};

function open() {
  renderApp("/b/1/projects/9");
}

afterEach(() => vi.unstubAllGlobals());

test("the project shows what is left to spend per stage, and warns when it is more than the budget has left", async () => {
  fakeServer({ ...base, "GET /projects/9/estimate": [200, estimate] });
  open();
  expect(await screen.findByText(/To finish: up to 46 credits · 30 credits left in the budget/)).toBeInTheDocument();
  expect(screen.getByText("That is more than is left. The owner has to approve the extra.")).toBeInTheDocument();
  const list = screen.getByRole("list", { name: "Credits left per stage" });
  expect(within(list).getByText("done")).toBeInTheDocument();
  expect(within(list).getByText("40 credits")).toBeInTheDocument();
  expect(within(list).getByText("free")).toBeInTheDocument(); // not "0 credits"
  expect(within(list).getByText("30 s at 480p, 1 credit a second")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$/);
});

test("when everything is paid for it says nothing is left to spend", async () => {
  fakeServer({ ...base, "GET /projects/9/estimate": [200, { ...estimate, stages: [{ stage: "video", done: true, credits: 0, note: "" }], remaining_credits: 0 }] });
  open();
  expect(await screen.findByText(/Nothing left to spend\. · 30 credits left in the budget/)).toBeInTheDocument();
  expect(screen.queryByText(/more than is left/)).not.toBeInTheDocument();
});

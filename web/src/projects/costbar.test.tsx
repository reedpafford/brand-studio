import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { ActionBarProvider, useActionBarSlot } from "../shell/ActionBar";
import { CostBarProvider, useCostBarAction, type CostAction } from "./CostBar";

afterEach(() => vi.unstubAllGlobals());

function Step({ action }: { action: CostAction | null }) {
  useCostBarAction(action);
  return <p>The step</p>;
}
function Slot() {
  const { setNode } = useActionBarSlot();
  return <div data-testid="phone-bar" ref={setNode} />;
}
function show(action: CostAction | null, fallback: CostAction | null = null, week: { used: number; allowed: number } | null = null) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ActionBarProvider>
        <CostBarProvider projectId={9} used={412} budget={660} pct={62} week={week} fallback={fallback}>
          <Step action={action} />
        </CostBarProvider>
        <Slot />
      </ActionBarProvider>
    </QueryClientProvider>,
  );
}
const estimate = { "GET /projects/9/estimate": [200, { remaining_credits: 140, stages: [] }] as [number, unknown] };

test("the bar says the budget, what finishing costs, the step's one amber and what the press leaves", async () => {
  setViewport(1440);
  fakeServer(estimate);
  const press = vi.fn();
  show({ label: "Make the takes", price: 54, onPress: press });
  const bar = screen.getByRole("region", { name: "Cost" });
  expect(within(bar).getByText(/412 \/ 660 credits · 62%/)).toBeInTheDocument();
  expect(await within(bar).findByText("To finish: up to 140 credits · 248 left")).toBeInTheDocument();
  expect(within(bar).getByText("This press leaves 194")).toBeInTheDocument();
  await userEvent.click(within(bar).getByRole("button", { name: "Make the takes · 54 credits" }));
  expect(press).toHaveBeenCalledOnce();
  expect(document.body.textContent).not.toMatch(/\$/); // credits only (rule 4)
});

test("a press that can't go says why where the amber is, and the step's own press wins over Next", async () => {
  setViewport(1440);
  fakeServer(estimate);
  show({ label: "Make the takes", price: 900, reason: "That's more than this video's budget.", onPress: () => {} }, { label: "Next: Final cut", onPress: () => {} });
  const make = screen.getByRole("button", { name: "Make the takes · 900 credits" });
  expect(make).toBeDisabled();
  expect(make).toHaveAccessibleDescription("That's more than this video's budget.");
  expect(screen.queryByText(/This press leaves/)).toBeNull();
  expect(screen.queryByRole("button", { name: /Next/ })).toBeNull();
});

test("on a phone the bar sits in the action bar above the tabs; an editor's own script shows the week", async () => {
  setViewport(390);
  fakeServer(estimate);
  show(null, { label: "Next: Assets", onPress: () => {} }, { used: 40, allowed: 145 });
  const phone = screen.getByTestId("phone-bar");
  expect(await within(phone).findByRole("button", { name: "Next: Assets" })).toBeInTheDocument();
  expect(within(phone).getByText("This week: 40 of 145 credits")).toBeInTheDocument();
});

test("one credit left to finish says credit", async () => {
  setViewport(1440);
  fakeServer({ "GET /projects/9/estimate": [200, { remaining_credits: 1, stages: [] }] });
  show(null);
  expect(await screen.findByText("To finish: up to 1 credit · 248 left")).toBeInTheDocument();
});

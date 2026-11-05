import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { editor } from "../test/people";
import { CostBarProvider, useCostBarAction, type CostAction } from "./CostBar";

afterEach(() => vi.unstubAllGlobals());

function Step({ action }: { action: CostAction | null }) {
  useCostBarAction(action);
  return <p>The step</p>;
}
function show(action: CostAction | null, fallback: CostAction | null = null) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CostBarProvider used={412} budget={660} fallback={fallback}>
        <Step action={action} />
      </CostBarProvider>
    </QueryClientProvider>,
  );
}

test("a step's one press sits at the foot of its tab, priced; the money is in the header, so no meter here", async () => {
  setViewport(1440);
  fakeServer({});
  const press = vi.fn();
  show({ label: "Make the takes", price: 54, onPress: press });
  const bar = screen.getByRole("region", { name: "Step press" });
  await userEvent.click(within(bar).getByRole("button", { name: "Make the takes · 54 credits" }));
  expect(press).toHaveBeenCalledOnce();
  expect(bar.textContent).not.toMatch(/\/ 660|credits left|To finish/);
  expect(document.body.textContent).not.toMatch(/\$/); // credits only (rule 4)
});

test("a press that can't go says why, and the step's own press wins over the fallback", () => {
  setViewport(1440);
  fakeServer({});
  show({ label: "Make the takes", price: 900, reason: "That's more than this video's budget.", onPress: () => {} }, { label: "Update everything after this", onPress: () => {} });
  const make = screen.getByRole("button", { name: "Make the takes · 900 credits" });
  expect(make).toBeDisabled();
  expect(make).toHaveAccessibleDescription("That's more than this video's budget.");
  expect(screen.queryByRole("button", { name: /Update everything/ })).toBeNull();
});

test("an editor's press past the budget is sent to the owner, never refused, and nothing is charged until they say yes", async () => {
  setViewport(390);
  fakeServer({ "GET /auth/me": [200, editor] });
  show({ label: "Make the takes", price: 300, onPress: () => {} });
  expect(await screen.findByRole("button", { name: "Send for approval · 300 credits" })).toBeEnabled();
  expect(screen.getByText("Goes past the video's budget. Nothing is charged until the owner says yes.")).toBeInTheDocument();
});

test("with no press there's no bar", () => {
  setViewport(1440);
  fakeServer({});
  show(null);
  expect(screen.queryByRole("region", { name: "Step press" })).toBeNull();
});

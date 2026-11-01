import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { ToastProvider } from "../toast";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { HeldRequests, type HeldWhere } from "./HeldRequests";

const job = (o: object = {}) => ({ id: 50, kind: "video", project_id: 9, script_id: null, credits: 27, status: "needs_owner_approval", created_at: new Date().toISOString(), finished_at: null, prompt_summary: "", step: "clip_take", error: "", held: "That's more than this video's budget.", declined: false, created_by_name: "Eli", waiting: "", auto: false, output: null, ...o });
function show(where: HeldWhere) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ToastProvider>
        <HeldRequests where={where} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}
afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

test("at 390, a held press on this video says Waiting for approval with why, and Withdraw cancels it for nothing", async () => {
  setViewport(390);
  const calls = fakeServer({ "GET /jobs": [200, [job(), job({ id: 51, project_id: 10 })]], "POST /jobs/50/cancel": [200, job({ status: "cancelled" })] });
  show({ projectId: 9 });
  const banner = (await screen.findByText("Waiting for approval")).closest("[role]") ?? document.body;
  expect(screen.getAllByText("Waiting for approval")).toHaveLength(1); // the other video's request isn't here
  expect(document.body).toHaveTextContent("A new take · 27 credits. That's more than this video's budget.");
  expect(document.body.textContent).not.toMatch(/ask (Reed|the owner)/i);
  await userEvent.click(within(banner as HTMLElement).getByRole("button", { name: "Withdraw" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /jobs/50/cancel")).toBe(true));
  expect(await screen.findByText("Withdrawn. Nothing was charged.")).toBeInTheDocument();
});

test("a declined request says the owner said no, with their reason, until OK", async () => {
  setViewport(1440);
  fakeServer({ "GET /jobs": [200, [job({ status: "cancelled", declined: true, held: "", error: "Over budget this week" })]] });
  show({ projectId: 9 });
  expect(await screen.findByText("The owner said no: Over budget this week")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "OK" }));
  expect(screen.queryByText(/The owner said no/)).toBeNull();
});

test("a decline with no reason doesn't repeat the server's own words", async () => {
  fakeServer({ "GET /jobs": [200, [job({ status: "cancelled", declined: true, held: "", error: "The owner said no this time. Nothing was charged." })]] });
  show({ projectId: 9 });
  expect(await screen.findByText("The owner said no")).toBeInTheDocument();
});

test("a held song take on a script shows on that script; Quick clips show only on Quick clip", async () => {
  fakeServer({ "GET /jobs": [200, [job({ id: 60, project_id: null, script_id: 7, step: null, held: "That's more than this script's budget." }), job({ id: 61, project_id: null, script_id: null, step: null, held: "That's more than this week's 97 credits." })]] });
  show({ scriptId: 7 });
  expect(await screen.findByText(/this script's budget/)).toBeInTheDocument();
  expect(screen.queryByText(/97 credits/)).toBeNull();
});

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "o@b.co", name: "Olu", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, role: "editor" };
const english = { id: "en", name: "English", on: true };
const spanish = { id: "es", name: "Spanish", on: false };
const sample = (o: object = {}) => ({ status: "none", text: null, reason: null, credits: 3, language: spanish, test_site: null, ...o });
const words = "[Hook]\nMAYA: ¿Sabes qué le pasó a mi perro?";
const routes = (o: Record<string, [number, unknown]> = {}) => ({
  "GET /auth/me": [200, owner] as [number, unknown],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]] as [number, unknown],
  "GET /languages": [200, [english, spanish]] as [number, unknown],
  ...o,
});

function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/languages"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("an Off language offers Test Spanish at its price for the brand; English is always on", async () => {
  setViewport(390);
  const calls = fakeServer(routes({ "GET /languages/es/sample": [200, sample()], "POST /languages/es/sample": [201, sample({ status: "making" })] }));
  open();
  const card = await screen.findByLabelText("Spanish");
  expect(within(card).getByText("Off for editors")).toBeInTheDocument();
  await userEvent.click(await within(card).findByRole("button", { name: /Test Spanish · 3 credits/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /languages/es/sample")?.body).toEqual({ brand_id: 1 }));
  expect(within(screen.getByLabelText("English")).getByText("English is always on.")).toBeInTheDocument();
});

test("a written test is shown to read, then Switch on for editors, with Undo", async () => {
  setViewport(1440);
  const calls = fakeServer(routes({ "GET /languages/es/sample": [200, sample({ status: "ready", text: words })], "PATCH /languages/es": [200, { ...spanish, on: true }] }));
  open();
  const card = await screen.findByLabelText("Spanish");
  expect(await within(card).findByLabelText("Spanish test script")).toHaveTextContent("¿Sabes qué le pasó a mi perro?");
  await userEvent.click(within(card).getByRole("button", { name: "Switch on for editors" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /languages/es")?.body).toEqual({ on: true }));
  expect(await screen.findByText("Spanish is on for editors.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PATCH /languages/es").at(-1)?.body).toEqual({ on: false }));
});

test("an On language offers Switch off; new scripts then start in English", async () => {
  setViewport(390);
  fakeServer(routes({ "GET /languages": [200, [english, { ...spanish, on: true }]], "GET /languages/es/sample": [200, sample({ status: "ready", text: words })], "PATCH /languages/es": [200, spanish] }));
  open();
  const card = await screen.findByLabelText("Spanish");
  await userEvent.click(await within(card).findByRole("button", { name: "Switch off" }));
  expect(await screen.findByText("Spanish is off for editors. Scripts in it keep it; new scripts start in English.")).toBeInTheDocument();
});

test("Reject keeps it off, with Undo; a rejected test offers Test again", async () => {
  setViewport(1440);
  const calls = fakeServer(routes({ "GET /languages/es/sample": [200, sample({ status: "ready", text: words })], "PATCH /languages/es/sample": [200, sample({ status: "rejected", text: words })] }));
  open();
  const card = await screen.findByLabelText("Spanish");
  await userEvent.click(await within(card).findByRole("button", { name: "Reject" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /languages/es/sample")?.body).toEqual({ rejected: true }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PATCH /languages/es/sample").at(-1)?.body).toEqual({ rejected: false }));
});

test("a failed test says why with Try again; the test site says first if it's a stand-in", async () => {
  setViewport(390);
  const note = "Test site: the budget for real language tests is used up, so this test will be a stand-in.";
  fakeServer(routes({ "GET /languages/es/sample": [200, sample({ status: "failed", reason: "The test didn't finish. Nothing was charged for it.", test_site: note })] }));
  open();
  const card = await screen.findByLabelText("Spanish");
  expect(await within(card).findByText("The test didn't finish. Nothing was charged for it.")).toBeInTheDocument();
  expect(within(card).getByText(note)).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: /Try again · 3 credits/ })).toBeInTheDocument();
});

test("a card whose test couldn't load says why with Try again", async () => {
  setViewport(390);
  const calls = fakeServer(routes({ "GET /languages/es/sample": [500, { detail: "Something went wrong." }] }));
  open();
  const card = await screen.findByLabelText("Spanish");
  await userEvent.click(await within(card).findByRole("button", { name: "Try again" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /languages/es/sample").length).toBeGreaterThan(1));
});

test("editors don't get the Languages page", async () => {
  setViewport(1440);
  fakeServer(routes({ "GET /auth/me": [200, editor] }));
  open();
  expect(await screen.findByText("Only the owner manages languages.")).toBeInTheDocument();
});

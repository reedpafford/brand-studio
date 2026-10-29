import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { renderApp } from "../test/render";
import { editor } from "../test/people";

const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 60, credits_used: 0, budget_pct: 0, created_by_id: 2,
};
const v2 = { version: 2, source: "upload", words: 12, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "SCENE 1 — KITCHEN\nMIA: Wait… it dipped?" };
const v1 = { version: 1, source: "paste", words: 3, created_by_id: 2, created_at: "2026-10-22T10:00:00Z", text: "First draft line" };
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
};

function open() {
  renderApp("/b/1/projects/9?tab=script");
}

afterEach(() => vi.unstubAllGlobals());

test("with no script yet you can paste one and it is saved as a version", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/script": [404, { detail: "This project has no script yet." }], "PUT /projects/9/script": [200, v1] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Paste it in" }));
  await userEvent.type(screen.getByLabelText("Your script"), "MIA: Wait… it dipped?");
  await userEvent.click(screen.getByRole("button", { name: "Save script" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/script")).toBe(true));
  expect(calls.find((c) => c.key === "PUT /projects/9/script")?.body).toEqual({ text: "MIA: Wait… it dipped?" });
});

test("the script shows line by line with its version, words and source", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [200, v2] });
  open();
  const lines = await screen.findByRole("list", { name: "Script text" });
  expect(within(lines).getAllByRole("listitem")).toHaveLength(2);
  expect(within(lines).getByText("MIA: Wait… it dipped?")).toBeInTheDocument();
  expect(screen.getByText(/12 words · uploaded · Saved/)).toBeInTheDocument();
});

test("a document upload becomes a new version, and a refused one shows the reason", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/script": [200, v2], "POST /projects/9/script/upload": [422, { detail: "That PDF looks like a scan, so there is no text to read." }] });
  open();
  await userEvent.upload(await screen.findByLabelText("Script file"), new File(["x"], "scan.pdf", { type: "application/pdf" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("That PDF looks like a scan, so there is no text to read.");
  expect(calls.some((c) => c.key === "POST /projects/9/script/upload")).toBe(true);
});

test("history lists versions; looking at an old one swaps Edit for Restore, and restoring can be undone", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/script": [200, v2],
    "GET /projects/9/script/versions": [200, [v2, v1].map((v) => ({ ...v, text: undefined }))],
    "GET /projects/9/script/versions/1": [200, v1],
    "PUT /projects/9/script": [200, { ...v1, version: 3 }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Versions" }));
  await userEvent.click(await screen.findByRole("menuitemradio", { name: /pasted · 3 words/ }));
  expect(await screen.findByText("First draft line")).toBeInTheDocument();
  expect(screen.getByText("You're looking at an older version.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Restore this version" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Restored an earlier version.");
  expect(calls.filter((c) => c.key === "PUT /projects/9/script").at(-1)?.body).toEqual({ text: "First draft line" });
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PUT /projects/9/script")).toHaveLength(2));
  expect(calls.filter((c) => c.key === "PUT /projects/9/script").at(-1)?.body).toEqual({ text: v2.text });
});

test("Back to the latest returns to the newest version", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/script": [200, v2],
    "GET /projects/9/script/versions": [200, [v2, v1].map((v) => ({ ...v, text: undefined }))],
    "GET /projects/9/script/versions/1": [200, v1],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Versions" }));
  await userEvent.click(await screen.findByRole("menuitemradio", { name: /pasted · 3 words/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Back to the latest" }));
  expect(await screen.findByRole("button", { name: "Edit" })).toBeInTheDocument();
});

test("editing saves the new words as the next version", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/script": [200, v2], "PUT /projects/9/script": [200, { ...v2, version: 3 }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
  const box = screen.getByLabelText("Your script");
  await userEvent.type(box, " Extra.");
  await userEvent.click(screen.getByRole("button", { name: "Save script" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/script")).toBe(true));
  expect(calls.find((c) => c.key === "PUT /projects/9/script")?.body).toEqual({ text: "SCENE 1 — KITCHEN\nMIA: Wait… it dipped? Extra." });
});

test("tagged direction lines look different from dialogue, and the dialogue is untouched", async () => {
  const withDirections = { ...v2, text: "MIA: Wait… it dipped?\n[Reaction] Mia's eyes widen.\n[Brand screen] fomo screen: Chart down" };
  fakeServer({ ...base, "GET /projects/9/script": [200, withDirections] });
  open();
  const list = await screen.findByRole("list", { name: "Script text" });
  const items = within(list).getAllByRole("listitem");
  expect(items).toHaveLength(3);
  expect(items[0]).toHaveTextContent("MIA: Wait… it dipped?");
  expect(items[0]).not.toHaveAttribute("data-direction");
  expect(items[1]).toHaveAttribute("data-direction", "Reaction");
  expect(items[1]).toHaveTextContent("▸ Mia's eyes widen.");
  expect(items[1]).toHaveTextContent("Reaction");
  expect(items[2]).toHaveAttribute("data-direction", "Brand screen");
  expect(items[2]).toHaveTextContent("★ fomo screen: Chart down");
});

const none = { ...base, "GET /projects/9/script": [404, { detail: "none" }] as [number, unknown], "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]] as [number, unknown] };
const draftJob = (o: object) => ({ id: 70, kind: "write-claude", step: "script_draft", project_id: 9, status: "succeeded", credits: 3, created_at: new Date().toISOString(), ...o });

test("with no script, Claude can write drafts from the brief, with the cost shown", async () => {
  const calls = fakeServer({ ...none, "GET /jobs": [200, []], "GET /projects/9/script/drafts": [200, []], "POST /projects/9/script/draft": [201, draftJob({ status: "queued" })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Write drafts · up to 3 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/script/draft")).toBe(true));
});

test("Write drafts rounds an owner's rate up, never below the charge (2.04 reads 3 credits)", async () => {
  fakeServer({ ...none, "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 2.04 }]], "GET /jobs": [200, []], "GET /projects/9/script/drafts": [200, []] });
  open();
  expect(await screen.findByRole("button", { name: "Write drafts · up to 3 credits" })).toBeInTheDocument();
});

test("finished drafts show their hook idea and script, and Use this draft makes it the working script", async () => {
  const calls = fakeServer({
    ...none,
    "GET /jobs": [200, [draftJob({})]],
    "GET /projects/9/script/drafts": [200, [{ job_id: 70, n: 1, hook_idea: "A cold open", script: "MIA: Wait… it dipped?" }, { job_id: 70, n: 2, hook_idea: "A warm open", script: "DEX: Look at that." }]],
    "POST /projects/9/script/drafts/70/2/use": [201, v1],
  });
  open();
  const second = await screen.findByLabelText("Draft 2");
  expect(within(second).getByText("Hook idea: A warm open")).toBeInTheDocument();
  expect(within(second).getByText("DEX: Look at that.")).toBeInTheDocument();
  expect(within(second).getByRole("button", { name: "Show all" })).toBeInTheDocument();
  await userEvent.click(within(second).getByRole("button", { name: "Use this draft" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/script/drafts/70/2/use")).toBe(true));
});

test("while Claude writes drafts the button says so and cannot be pressed twice; a failure says credits came back", async () => {
  fakeServer({ ...none, "GET /jobs": [200, [draftJob({ status: "running" })]], "GET /projects/9/script/drafts": [200, []] });
  open();
  expect(await screen.findByText(/Writing drafts…/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Write drafts/ })).not.toBeInTheDocument();
});

test("a failed draft run says credits came back and offers another go", async () => {
  fakeServer({ ...none, "GET /jobs": [200, [draftJob({ status: "failed" })]], "GET /projects/9/script/drafts": [200, []] });
  open();
  expect(await screen.findByText("The drafts didn't finish.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Write drafts/ })).toBeEnabled();
});

test("over the video's budget an editor's drafts button is off, with the reason", async () => {
  fakeServer({ ...none, "GET /projects/9": [200, { ...project, credits_used: 59, budget_credits: 60 }], "GET /jobs": [200, []], "GET /projects/9/script/drafts": [200, []] });
  open();
  const write = await screen.findByRole("button", { name: /^Write drafts · up to 3 credits/ });
  expect(write).toBeDisabled();
  expect(write).toHaveAccessibleDescription("That's more than this video's budget.");
});

test("with no script there are two ways to start, side by side: write it with Claude, or upload your own", async () => {
  fakeServer({ ...none, "GET /jobs": [200, []], "GET /projects/9/script/drafts": [200, []] });
  open();
  expect(await screen.findByRole("heading", { name: "Write it with Claude" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Upload your own" })).toBeInTheDocument();
  expect(screen.getByText("Upload a file")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Paste it in" })).toBeInTheDocument();
});

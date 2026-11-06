import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { CastOk } from "./CastOk";

afterEach(() => vi.unstubAllGlobals());

const item = (over: object) => ({
  ref: "char:12", kind: "character", name: "Nate", library_item_id: 12, version: 1, source: "video", preview_file_id: 7,
  readiness: "ready", approval: "new", sig: "abc", clip_ids: ["c1"], changes: [], voice: null, was_voice: null,
  made_by: "director", made_at: null, revised_by: null, revised_at: null, revised_why: null, was_preview_file_id: null, ...over,
});
const cast = (over: object) => ({
  state: "ready", approved_by: null, approved_at: null, asked: true, can_approve: true, waiting: ["Nate", "Roof"], not_ready: [], paused_clips: ["c1"],
  items: [item({}), item({ ref: "place:3", kind: "place", name: "Roof", library_item_id: 3, source: "library", sig: "def" })],
  update: { stills: [], clips: [], credits: 0, clips_credits: 0, kept_items: [] },
  previews: { credits: 2, usd: null, budget_credits: 40, budget_usd: null }, ...over,
});
const show = () => render(<QueryClientProvider client={new QueryClient()}><CastOk projectId={9} /></QueryClientProvider>);

test("the director's ask shows the whole set with its previews, and one press approves exactly what was shown", async () => {
  const calls = fakeServer({ "GET /projects/9/cast": [200, cast({})], "POST /projects/9/cast/approve": [200, cast({ state: "approved", asked: false })] });
  show();
  expect(await screen.findByRole("img", { name: "Nate" })).toBeTruthy();
  expect(screen.getByText("From the brand's library")).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Approve cast & places" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/cast/approve")?.body).toEqual({ seen: { "char:12": "abc", "place:3": "def" } }));
});

test("a set ready with no director asking still has its press", async () => {
  fakeServer({ "GET /projects/9/cast": [200, cast({ asked: false })] });
  show();
  expect(await screen.findByRole("button", { name: "Approve cast & places" })).toBeTruthy();
  expect(screen.queryByText(/The director is waiting/)).toBeNull();
});

test("someone who may not approve it sees no press", async () => {
  const calls = fakeServer({ "GET /projects/9/cast": [200, cast({ can_approve: false })] });
  show();
  await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /projects/9/cast")).toBe(true));
  expect(screen.queryByRole("button", { name: "Approve cast & places" })).toBeNull();
});

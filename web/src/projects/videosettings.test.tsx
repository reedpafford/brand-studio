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
const settings = {
  fields: [
    { key: "shape", label: "Shape", value: "9:16", value_label: "9:16", price_label: null, choices: [{ id: "9:16", label: "9:16", on: true }, { id: "1:1", label: "1:1", on: true }] },
    { key: "look", label: "Look", value: "house", value_label: "House", price_label: null, choices: [{ id: "house", label: "House", on: true }] },
    {
      key: "video_model", label: "Video model", value: "auto", value_label: "Auto", price_label: "1 credit a second",
      choices: [
        { id: "auto", label: "Auto", price_label: "1 credit a second", on: true },
        { id: "seedance-2.0", label: "Seedance 2.0", price_label: "0.6 credits a second", on: true, no_lip_sync: true },
        { id: "veo-4", label: "Veo 4", price_label: "4 credits a second", on: true, over_cap: true },
        { id: "test-model", label: "Untested model", price_label: "1 credit a second", on: false },
      ],
    },
    { key: "picture_model", label: "Picture model", value: "auto", value_label: "Auto", price_label: "1.2 credits a still", choices: [{ id: "auto", label: "Auto", on: true }] },
  ],
  language: { label: "Spanish", from: "script" },
};
const preview = { to_finish_credits: 30, was_credits: 24, stills_out_of_date: 0, clips_out_of_date: 2, sung_to_broll: 3, over_budget: false, over_cap: false, reason: null };
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Bo eats." }],
  "GET /projects/9/breakdown": [200, { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [], clips: [] } }],
  "GET /projects/9/storyboard": [200, []],
  "GET /projects/9/clips": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /projects/9/assets": [200, []],
  "GET /jobs": [200, []],
  "GET /looks": [404, { detail: "none" }],
  "GET /projects/9/settings": [200, settings],
  "POST /projects/9/settings/preview": [200, preview],
  "POST /projects/9/settings": [200, { settings, was: "auto" }],
};

function open(query = "?step=cast") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/videos/9${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("the Video settings row shows each choice and its price, and the language read only from the script (flows VS1)", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  const row = await screen.findByRole("region", { name: "Video settings" });
  expect(within(row).getByRole("button", { name: /Shape: 9:16/ })).toBeInTheDocument();
  expect(within(row).getByRole("button", { name: /Video model: Auto.*· 1 credit a second/ })).toBeInTheDocument();
  expect(within(row).getByText("Language: Spanish (from the script)")).toBeInTheDocument();
  expect(within(row).queryByRole("button", { name: /Language/ })).toBeNull(); // read only
  expect(document.body.textContent).not.toMatch(/\$/);
});

test("a picker lists choices with prices, says No lip-sync, greys one over the video limit, and hides the off ones from an editor", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Video model: Auto/ }));
  const seedance = await screen.findByRole("button", { name: /Seedance 2.0/ });
  expect(seedance).toHaveTextContent("0.6 credits a second");
  expect(within(seedance).getByText("No lip-sync")).toBeInTheDocument();
  const veo = screen.getByRole("button", { name: /Veo 4/ });
  expect(veo).toBeDisabled();
  expect(veo).toHaveTextContent("Over the video limit");
  expect(screen.queryByText("Untested model")).toBeNull();
});

test("picking previews the switch: Sung to B-roll, what goes out of date and the new total; Switch applies it, and Undo puts it back", async () => {
  setViewport(1440);
  const calls = fakeServer(base);
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Video model: Auto/ }));
  await userEvent.click(await screen.findByRole("button", { name: /Seedance 2.0/ }));
  const ask = await screen.findByRole("alertdialog", { name: "Switch to Seedance 2.0?" });
  expect(await within(ask).findByText("Seedance 2.0 can't lip-sync. Your 3 Sung shots become B-roll (picture only).")).toBeInTheDocument();
  expect(within(ask).getByText(/2 clips already made stay as they are and show Out of date/)).toBeInTheDocument();
  expect(within(ask).getByText("To finish: about 30 credits (was 24).")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /projects/9/settings/preview")?.body).toEqual({ key: "video_model", value: "seedance-2.0" });
  await userEvent.click(within(ask).getByRole("button", { name: "Switch" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/settings")?.body).toEqual({ key: "video_model", value: "seedance-2.0" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /projects/9/settings").map((c) => c.body)).toContainEqual({ key: "video_model", value: "auto" }));
});

test("over the budget, Switch is disabled with the reason and the picker stays open", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "POST /projects/9/settings/preview": [200, { ...preview, over_budget: true, reason: "That's more than this video's budget." }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Video model: Auto/ }));
  await userEvent.click(await screen.findByRole("button", { name: /Seedance 2.0/ }));
  const ask = await screen.findByRole("alertdialog", { name: "Switch to Seedance 2.0?" });
  const go = await within(ask).findByRole("button", { name: "Switch" });
  await vi.waitFor(() => expect(go).toBeDisabled());
  expect(within(ask).getByText("That's more than this video's budget.")).toBeInTheDocument();
  await userEvent.click(within(ask).getByRole("button", { name: "Not yet" }));
  expect(screen.getByRole("button", { name: /Seedance 2.0/ })).toBeInTheDocument(); // the picker is still open
  expect(calls.some((c) => c.key === "POST /projects/9/settings")).toBe(false);
});

test("on a finished video the warning that the final cut stays downloadable comes first", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }], "GET /projects/9/clips": [200, [{ id: 3, clip_id: "c1", seconds: 8, prompt: "p", references: [], problems: [], kept: [], file_id: 61, takes: [{ id: 2 }], picked_take_id: 2, approved: true, stale: false, take_credits: 24, inserts: [] }]] });
  open("?step=downloads");
  await userEvent.click(await screen.findByRole("button", { name: /Shape: 9:16/ }));
  await userEvent.click(await screen.findByRole("button", { name: "1:1" }));
  const ask = await screen.findByRole("alertdialog", { name: "Change to 1:1?" });
  const first = (await within(ask).findAllByText(/./, { selector: "p" }))[0];
  expect(first).toHaveTextContent(/^This video is finished\. Changing the shape puts 2 clips out of date; your current final cut stays downloadable until you make a new one\.$/);
});

test("on a phone the row is one line that opens a sheet with the settings", async () => {
  setViewport(390);
  fakeServer(base);
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Settings: 9:16 · House · Auto · Auto" }));
  const sheet = await screen.findByRole("dialog", { name: "Video settings" });
  expect(within(sheet).getByRole("button", { name: /Video model: Auto/ })).toBeInTheDocument();
  expect(within(sheet).getByText("Language: Spanish (from the script)")).toBeInTheDocument();
});

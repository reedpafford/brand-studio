import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, name: "Eli", role: "editor" };
const mia = { id: 5, kind: "character", name: "Mia", notes: "", brand_ids: [1], image_file_ids: [9], outfits: [], version: 3, sheet_file_id: 71, sheet_status: "approved" };
const sheets = [
  { file_id: 72, look_id: "pixar", made_at: "2026-10-29T10:00:00Z", preferred: true },
  { file_id: 71, look_id: "house", made_at: "2026-10-28T10:00:00Z", preferred: true },
  { file_id: 70, look_id: "house", made_at: "2026-10-27T10:00:00Z", preferred: false },
];
const server = (me: object, o: Record<string, [number, unknown]> = {}) => ({
  "GET /auth/me": [200, me] as [number, unknown],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]] as [number, unknown],
  "GET /team/members": [200, []] as [number, unknown],
  "GET /library/character": [200, []] as [number, unknown],
  "GET /library/character/5": [200, mia] as [number, unknown],
  "GET /library/character/5/versions": [200, []] as [number, unknown],
  "GET /looks": [200, [{ id: "house", name: "House", blurb: "", on: true, sample_still_id: null }, { id: "pixar", name: "Disney Pixar", blurb: "", on: true, sample_still_id: null }]] as [number, unknown],
  "GET /library/character/5/sheet/versions": [200, sheets] as [number, unknown],
  ...o,
});
function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/library/characters/5"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("the owner sees each approved sheet with its look, picks another to use (free), and Undo puts the first back", async () => {
  setViewport(390);
  const calls = fakeServer(server(owner, { "POST /library/character/5/sheet/preferred": [200, { ...mia, sheet_file_id: 70, was_file_id: 71 }] }));
  open();
  const list = await screen.findByRole("region", { name: "Sheets" });
  expect(within(list).getAllByText("In use")).toHaveLength(2); // one per look
  const older = within(list).getByRole("listitem", { name: "Sheet 70" });
  await userEvent.click(within(older).getByRole("button", { name: "Use this one" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /library/character/5/sheet/preferred")?.body).toEqual({ file_id: 70, look_id: "house" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /library/character/5/sheet/preferred").at(-1)?.body).toEqual({ file_id: 71, look_id: "house" }));
});

test("an editor sees which sheet is in use, with no press", async () => {
  setViewport(1440);
  fakeServer(server(editor));
  open();
  const list = await screen.findByRole("region", { name: "Sheets" });
  expect(within(list).getByText("Videos use the sheet marked In use. Only the owner picks another.")).toBeInTheDocument();
  expect(within(list).queryByRole("button", { name: "Use this one" })).toBeNull();
});

test("with one sheet, or a server without versions, there's no list", async () => {
  setViewport(1440);
  fakeServer(server(owner, { "GET /library/character/5/sheet/versions": [404, { detail: "Not Found" }] }));
  open();
  expect(await screen.findByDisplayValue("Mia")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Sheets" })).toBeNull();
});

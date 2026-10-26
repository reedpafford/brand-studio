import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, name: "Eli", role: "editor" };
const brands = [{ id: 1, name: "fomo", colours: [] }, { id: 2, name: "Iron Paws", colours: [] }];
const mia = { id: 5, kind: "character", name: "Mia", notes: "", brand_ids: [1], image_file_ids: [9], outfits: [], version: 3 };

function renderAt(path: string) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("lists characters for the brand and searches by name", async () => {
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /library/character": [200, [mia, { ...mia, id: 6, name: "Dex" }]] });
  renderAt("/b/1/library/characters");
  expect(await screen.findByText("Mia")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Search"), "dex");
  expect(screen.queryByText("Mia")).not.toBeInTheDocument();
  await userEvent.clear(screen.getByLabelText("Search"));
  await userEvent.type(screen.getByLabelText("Search"), "zzz");
  expect(screen.getByText(/Nothing matches "zzz"/)).toBeInTheDocument();
});

test("a new character is created in the current brand", async () => {
  const calls = fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /library/character": [200, []], "POST /library/character": [201, mia] });
  renderAt("/b/1/library/characters");
  expect(await screen.findByText("No characters for this brand yet.")).toBeInTheDocument();
  expect(screen.getByText("Add a character once, use them in every video.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "New character" }));
  await userEvent.type(screen.getByLabelText("Name"), "Mia");
  await userEvent.click(screen.getByRole("button", { name: "Create character" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character")).toBe(true));
  expect(calls.find((c) => c.key === "POST /library/character")?.body).toMatchObject({ name: "Mia", brand_ids: [1] });
});

test("saving a character sends its changes, and history can restore an old version", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, brands],
    "GET /team/members": [200, [{ id: 2, name: "Eli", email: "e@b.co", role: "editor" }]],
    "GET /library/character/5": [200, mia],
    "PATCH /library/character/5": [200, { ...mia, version: 4 }],
    "GET /library/character/5/versions": [200, [{ version: 3, snapshot: mia, saved_by_id: 2, created_at: "2026-10-23T10:00:00Z" }, { version: 2, snapshot: mia, saved_by_id: 2, created_at: "2026-10-20T10:00:00Z" }]],
    "POST /library/character/5/versions/2/restore": [200, { ...mia, version: 4 }],
  });
  renderAt("/b/1/library/characters/5");
  const name = await screen.findByLabelText("Name");
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  await userEvent.clear(name);
  await userEvent.type(name, "Mia R");
  await userEvent.click(screen.getByLabelText("Iron Paws"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PATCH /library/character/5")).toBe(true));
  expect(calls.find((c) => c.key === "PATCH /library/character/5")?.body).toMatchObject({ name: "Mia R", brand_ids: [1, 2] });
  await userEvent.click(await screen.findByRole("button", { name: "Restore v2" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character/5/versions/2/restore")).toBe(true));
  expect(await screen.findByRole("status")).toHaveTextContent("Restored v2 as v4.");
});

test("archived items: editors can bring them back, only the owner can delete forever", async () => {
  const archivedRoutes = { "GET /brands": [200, brands] as [number, unknown], "GET /library/character": [200, [mia]] as [number, unknown] };
  fakeServer({ "GET /auth/me": [200, editor], ...archivedRoutes });
  const view = render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/library/characters"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await userEvent.click(await screen.findByLabelText("Show archived"));
  expect(await screen.findByRole("button", { name: "Unarchive Mia" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /forever/ })).not.toBeInTheDocument();
  view.unmount();

  const calls = fakeServer({ "GET /auth/me": [200, owner], ...archivedRoutes, "DELETE /library/character/5/permanent": [204, null] });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderAt("/b/1/library/characters");
  await userEvent.click(await screen.findByLabelText("Show archived"));
  await userEvent.click(await screen.findByRole("button", { name: "Delete Mia forever" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /library/character/5/permanent")).toBe(true));
});

test("a character's outfits and voice are saved; places don't send them", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, brands],
    "GET /team/members": [200, []],
    "GET /library/character/5": [200, { ...mia, outfits: [{ name: "Gym", file_ids: [] }], voice_file_id: null }],
    "GET /library/character/5/versions": [200, []],
    "GET /library/place/7": [200, { ...mia, id: 7, kind: "place", name: "Cafe" }],
    "GET /library/place/7/versions": [200, []],
    "PATCH /library/character/5": [200, mia],
    "PATCH /library/place/7": [200, mia],
    "POST /files": [201, { id: 21, filename: "v.mp3", content_type: "audio/mpeg", size: 3, created_at: "2026-10-23T00:00:00Z" }],
  });
  renderAt("/b/1/library/characters/5");
  await userEvent.click(await screen.findByRole("button", { name: "Add outfit" }));
  await userEvent.type(screen.getByLabelText("Outfit 2 name"), "Office");
  await userEvent.upload(screen.getByLabelText("Voice file"), new File(["x"], "v.mp3", { type: "audio/mpeg" }));
  await screen.findByLabelText("Voice sample");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PATCH /library/character/5")).toBe(true));
  expect(calls.find((c) => c.key === "PATCH /library/character/5")?.body).toMatchObject({
    outfits: [{ name: "Gym", file_ids: [] }, { name: "Office", file_ids: [] }],
    voice_file_id: 21,
  });
});

test("places have no outfits or voice", async () => {
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /team/members": [200, []], "GET /library/place/7": [200, { ...mia, id: 7, kind: "place", name: "Cafe" }], "GET /library/place/7/versions": [200, []] });
  renderAt("/b/1/library/places/7");
  await screen.findByLabelText("Name");
  expect(screen.queryByRole("button", { name: "Add outfit" })).not.toBeInTheDocument();
});

test("archiving happens at once with a toast, and Undo brings the item back", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, brands],
    "GET /team/members": [200, []],
    "GET /library/character": [200, []],
    "GET /library/character/5": [200, mia],
    "GET /library/character/5/versions": [200, []],
    "DELETE /library/character/5": [204, null],
    "POST /library/character/5/unarchive": [200, mia],
  });
  renderAt("/b/1/library/characters/5");
  await userEvent.click(await screen.findByRole("button", { name: "Archive character" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Mia archived.");
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character/5/unarchive")).toBe(true));
});

test("shared items show their brands, and Save needs at least one brand", async () => {
  fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, brands],
    "GET /team/members": [200, []],
    "GET /library/character/5": [200, { ...mia, brand_ids: [1, 2] }],
    "GET /library/character/5/versions": [200, []],
  });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("Shared with Iron Paws. Changes apply there too.")).toBeInTheDocument();
  await userEvent.click(screen.getByLabelText("fomo"));
  expect(screen.getByText("This will remove Mia from fomo's library.")).toBeInTheDocument();
  await userEvent.click(screen.getByLabelText("Iron Paws"));
  expect(screen.getByText("Pick at least one brand.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
});

test("archived cards carry an Archived badge", async () => {
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /library/place": [200, [{ ...mia, kind: "place" }]] });
  renderAt("/b/1/library/places");
  await userEvent.click(await screen.findByLabelText("Show archived"));
  expect(await screen.findByText("Archived")).toBeInTheDocument();
});

test("a refused restore or delete-forever shows the server's reason", async () => {
  fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /library/character": [200, [mia]],
    "DELETE /library/character/5/permanent": [409, { detail: "Archive it first." }],
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderAt("/b/1/library/characters");
  await userEvent.click(await screen.findByLabelText("Show archived"));
  await userEvent.click(await screen.findByRole("button", { name: "Delete Mia forever" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Archive it first.");
});

test("a card without a picture is still linked by the item's name", async () => {
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /library/character": [200, [{ ...mia, image_file_ids: [] }]] });
  renderAt("/b/1/library/characters");
  expect(await screen.findByRole("link", { name: "Mia" })).toHaveAttribute("href", "/b/1/library/characters/5");
});

const sheetItem = { ...mia, source_photo_file_id: 20, sheet_file_id: null, sheet_status: "none" };
const sheetBase: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, brands],
  "GET /models": [200, [{ id: "nano-banana-pro", kind: "image", name: "Nano Banana Pro", credits_per_unit: { "2K": 1.5 } }]],
  "GET /jobs": [200, []],
  "GET /team/members": [200, []],
  "GET /library/character/5/versions": [200, []],
};

test("a character without a sheet offers to make one, with the server's price, and sends the job", async () => {
  const calls = fakeServer({ ...sheetBase, "GET /library/character/5": [200, sheetItem], "POST /library/character/5/sheet": [201, { id: 50, step: "sheet", library_item_id: 5, status: "queued" }] });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("Source photo, not used in videos")).toBeInTheDocument();
  expect(screen.getByText("Needs a sheet")).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Make house-style sheet · 2 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /library/character/5/sheet")?.body).toMatchObject({ model_id: "nano-banana-pro", change: "" }));
});

test("without a photo or notes a character says to upload one; with notes a sheet can be drawn from them", async () => {
  fakeServer({ ...sheetBase, "GET /library/character/5": [200, { ...sheetItem, source_photo_file_id: null, notes: "" }] });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("Upload a photo, or add notes, to make a sheet.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Make house-style sheet/ })).not.toBeInTheDocument();
});

test("a character with notes and no photo can make a sheet from the notes", async () => {
  fakeServer({ ...sheetBase, "GET /library/character/5": [200, { ...sheetItem, source_photo_file_id: null, notes: "A tired coach in a grey hoodie" }] });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("Make a sheet from the notes?")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Make house-style sheet/ })).toBeInTheDocument();
});

test("while drawing the card says so and offers nothing to press", async () => {
  fakeServer({ ...sheetBase, "GET /library/character/5": [200, { ...sheetItem, sheet_status: "drawing" }] });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("A sheet is being made.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Make house-style sheet|Approve|Redo/ })).not.toBeInTheDocument();
});

test("a sheet is approved, then shows as approved and can be undone", async () => {
  const calls = fakeServer({
    ...sheetBase,
    "GET /library/character/5": [200, { ...sheetItem, sheet_file_id: 21, sheet_status: "needs_approval" }],
    "POST /library/character/5/sheet/approve": [200, {}],
  });
  renderAt("/b/1/library/characters/5");
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character/5/sheet/approve")).toBe(true));
});

test("an approved sheet has the approved mark and Redo takes a note", async () => {
  const calls = fakeServer({
    ...sheetBase,
    "GET /library/character/5": [200, { ...sheetItem, sheet_file_id: 21, sheet_status: "approved" }],
    "POST /library/character/5/sheet": [201, { id: 51, step: "sheet", library_item_id: 5, status: "queued" }],
  });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("✓ Approved sheet")).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Redo · 2 credits" }));
  await userEvent.type(screen.getByLabelText(/What should change/), "Shorter hair");
  await userEvent.click(screen.getAllByRole("button", { name: "Redo · 2 credits" }).at(-1)!);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /library/character/5/sheet")?.body).toMatchObject({ change: "Shorter hair" }));
});

test("a failed sheet says credits came back and offers Try again", async () => {
  fakeServer({
    ...sheetBase,
    "GET /library/character/5": [200, sheetItem],
    "GET /jobs": [200, [{ id: 50, kind: "image", step: "sheet", library_item_id: 5, status: "failed", created_at: new Date().toISOString() }]],
  });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("Didn't finish · credits returned")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Try again/ })).toBeInTheDocument();
});

test("library cards say Needs a sheet until the sheet is approved", async () => {
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /library/character": [200, [{ ...mia, sheet_status: "none" }, { ...mia, id: 6, name: "Dex", sheet_status: "approved" }]] });
  renderAt("/b/1/library/characters");
  await screen.findByText("Dex");
  expect(screen.getAllByText("Needs a sheet")).toHaveLength(1);
});

test("Open Mia from a video comes back to the same stage", async () => {
  fakeServer({ ...sheetBase, "GET /library/character/5": [200, sheetItem] });
  renderAt("/b/1/library/characters/5?back=%2Fb%2F1%2Fprojects%2F9%3Fstage%3Dclips");
  expect(await screen.findByRole("link", { name: "← Back to your video" })).toHaveAttribute("href", "/b/1/projects/9?stage=clips");
});

test("a back link to somewhere else is ignored", async () => {
  fakeServer({ ...sheetBase, "GET /library/character/5": [200, sheetItem] });
  renderAt("/b/1/library/characters/5?back=https%3A%2F%2Fevil.example");
  expect(await screen.findByRole("link", { name: "← Characters" })).toHaveAttribute("href", "/b/1/library/characters");
});

test("a sheet held from before the limits changed says Not started, not Drawing, and offers nothing to press", async () => {
  fakeServer({ ...sheetBase, "GET /library/character/5": [200, { ...sheetItem, sheet_status: "waiting_for_owner" }] });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("Not started")).toBeInTheDocument();
  expect(screen.queryByText(/Drawing/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Make house-style sheet|Approve|Redo/ })).not.toBeInTheDocument();
});

test("past an editor's weekly allowance the sheet button is off and says why", async () => {
  fakeServer({ ...sheetBase, "GET /credits/me": [200, { quick_clip_credits_used: 144, quick_clip_credits_allowed: 145 }], "GET /library/character/5": [200, sheetItem] });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("You've used this week's 145 credits. It resets on Monday.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make house-style sheet · 2 credits" })).toBeDisabled();
});

test("a character's photo at creation is the source photo for its sheet, not a loose image", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, brands],
    "GET /library/character": [200, []],
    "POST /files": [201, { id: 33, filename: "nate.jpg", content_type: "image/jpeg", size: 3, created_at: "2026-10-23T00:00:00Z" }],
    "POST /library/character": [201, mia],
  });
  renderAt("/b/1/library/characters");
  await userEvent.click(await screen.findByRole("button", { name: "New character" }));
  await userEvent.type(screen.getByLabelText("Name"), "Nate");
  await userEvent.upload(screen.getByLabelText("Photo (optional)"), new File(["x"], "nate.jpg", { type: "image/jpeg" }));
  await userEvent.click(screen.getByRole("button", { name: "Create character" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /library/character")?.body).toMatchObject({ source_photo_file_id: 33, image_file_ids: [] }));
});

test("a character's page has no second Images box, since the sheet card holds the photo", async () => {
  fakeServer({ ...sheetBase, "GET /library/character/5": [200, sheetItem] });
  renderAt("/b/1/library/characters/5");
  await screen.findByText("House-style sheet");
  expect(screen.queryByText("Images")).not.toBeInTheDocument();
});

test("a card shows the sheet, else the source photo", async () => {
  fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, brands],
    "GET /library/character": [200, [{ ...mia, image_file_ids: [], source_photo_file_id: 20, sheet_file_id: 21, sheet_status: "approved" }, { ...mia, id: 6, name: "Dex", image_file_ids: [], source_photo_file_id: 22, sheet_file_id: null }]],
  });
  renderAt("/b/1/library/characters");
  await screen.findByText("Dex");
  const srcs = screen.getAllByRole("img").map((i) => i.getAttribute("src"));
  expect(srcs).toContain("/api/files/21");
  expect(srcs).toContain("/api/files/22");
});

test("when the server gives the whole press, the sheet button shows the most it can cost and the usual price under it", async () => {
  fakeServer({ ...sheetBase, "GET /library/character/5": [200, { ...sheetItem, sheet_credits: 4, change_credits: 5 }] });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByRole("button", { name: "Make house-style sheet · up to 4 credits" })).toBeInTheDocument();
  expect(await screen.findByText("Usually 2. Anything not used comes back.")).toBeInTheDocument();
});

test("a sheet that reads wrong on the character's page says so, and Fix it with a note opens the redo with the problem as its note", async () => {
  fakeServer({ ...sheetBase, "GET /library/character/5": [200, { ...sheetItem, sheet_file_id: 70, sheet_status: "needs_approval", look_fit: { seen: "a teenage boy", problem: "Mia is a woman in her 30s" } }] });
  renderAt("/b/1/library/characters/5");
  expect(await screen.findByText("This look reads as a teenage boy, but Mia is a woman in her 30s.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Fix it with a note" }));
  expect(await screen.findByLabelText("What should change? (optional)")).toHaveValue("Mia is a woman in her 30s");
});

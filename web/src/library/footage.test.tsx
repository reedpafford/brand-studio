import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { renderApp } from "../test/render";
import { owner } from "../test/people";
import { setViewport } from "../test/viewport";

// Footage folders (Reed, 10 Nov): nested as in his Drive, shown as breadcrumbs and folders with counts.
const folder = (id: number, name: string, parent_id: number | null) => ({ id, brand_id: 1, parent_id, name, created_by_id: 1, can_manage: true, items: { scripts: 0, videos: 0, clips: 0, footage: 0 } });
const clip = (id: number, description: string, folder_id: number | null, path: string) => ({ id, file_id: 70 + id, thumb_file_id: null, seconds: 4, description, product_id: null, describing: false, note: "", folder_id, folder: path });
const rows = [folder(1, "Product shots", null), folder(2, "Close-ups", 1), folder(3, "Lifestyle", null)];
const clips = [clip(10, "The alarm on a desk.", null, ""), clip(11, "The lid opening.", 1, "Product shots"), clip(12, "The red light, close.", 2, "Product shots/Close-ups")];

beforeEach(() => setViewport(1440));

function server(extra: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, [{ id: 1, name: "Resilia", colours: [] }]],
    "GET /library/prop": [200, []],
    "GET /brands/1/footage": [200, clips],
    "GET /brands/1/folders?footage=true": [200, rows],
    "GET /brands/1/footage/price": [200, { credits: 1, usd: 0.02 }],
    ...extra,
  });
}

test("Footage folders: the open folder's folders with their clips counted at any depth, its clips, crumbs back up; a search looks in every folder", async () => {
  const calls = server();
  renderApp("/b/1/library/footage");
  const here = await screen.findByRole("list", { name: "Folders here" });
  expect(within(here).getByRole("button", { name: /Product shots\s*2 clips/ })).toBeInTheDocument();
  expect(within(here).getByRole("button", { name: /Lifestyle\s*0 clips/ })).toBeInTheDocument();
  expect(screen.getByText("The alarm on a desk.")).toBeInTheDocument();
  expect(screen.queryByText("The lid opening.")).not.toBeInTheDocument();
  await userEvent.click(within(here).getByRole("button", { name: /Product shots/ }));
  expect(await screen.findByText("The lid opening.")).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Folders here" })).getByRole("button", { name: /Close-ups\s*1 clip$/ })).toBeInTheDocument();
  const crumbs = screen.getByRole("navigation", { name: "Folders" });
  expect(within(crumbs).getByRole("button", { name: "Product shots" })).toHaveAttribute("aria-current", "page");
  await userEvent.click(screen.getAllByRole("button", { name: "Add a clip" })[0]);
  expect(screen.getByText("To Product shots")).toBeInTheDocument(); // it lands in the open folder
  await userEvent.click(within(crumbs).getByRole("button", { name: "All footage" }));
  expect(await screen.findByText("The alarm on a desk.")).toBeInTheDocument();
  await userEvent.type(screen.getByRole("searchbox", { name: "Search the library" }), "red");
  const found = (await screen.findByText("The red light, close.")).closest("li")!;
  expect(within(found).getByText(/in Product shots\/Close-ups/)).toBeInTheDocument();
  expect(calls.every((c) => !c.key.startsWith("POST"))).toBe(true);
});

test("Footage folders: a clip moves to another folder with Undo; a deleted folder's clips go up a level, with Undo", async () => {
  const calls = server({
    "POST /folders/file": [200, { folder_id: 3, was: [{ id: 11, folder_id: 1 }] }],
    "DELETE /folders/2": [200, { moved: 1, ideas: 0 }],
    "POST /folders/2/restore": [200, rows[1]],
  });
  renderApp("/b/1/library/footage?folder=1");
  const card = (await screen.findByText("The lid opening.")).closest("li")!;
  await userEvent.click(within(card).getByRole("button", { name: "Move to…" }));
  await userEvent.click(await screen.findByRole("radio", { name: "Lifestyle" }));
  await userEvent.click(screen.getByRole("button", { name: "Move" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /folders/file").map((c) => c.body)).toEqual([{ kind: "footage", ids: [11], folder_id: 3 }, { kind: "footage", ids: [11], folder_id: 1 }]));
  await userEvent.click(within(screen.getByRole("list", { name: "Folders here" })).getByRole("button", { name: /Close-ups/ }));
  await userEvent.click(await screen.findByRole("button", { name: "More for Close-ups" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: /Delete folder/ }));
  expect(await screen.findByText(/Its 1 clip move up to Product shots\. No clip is deleted/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Delete folder" }));
  expect(await screen.findByText("Deleted “Close-ups”. Its 1 clip moved up to Product shots.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /folders/2/restore")).toBe(true));
});

test("Footage: a competitor's clip wears a Competitor badge; the card's toggle marks one, with no product", async () => {
  const theirs = { ...clip(13, "A cheap keychain alarm.", null, ""), competitor: true };
  const calls = server({ "GET /brands/1/footage": [200, [...clips, theirs]], "PATCH /brands/1/footage/10": [200, { ...clips[0], competitor: true }] });
  renderApp("/b/1/library/footage");
  const card = (await screen.findByText("A cheap keychain alarm.")).closest("li")!;
  expect(within(card).getByText("Competitor")).toBeInTheDocument();
  expect(within(card).getByText("Never shown as the brand’s")).toBeInTheDocument();
  const ours = screen.getByText("The alarm on a desk.").closest("li")!;
  expect(within(ours).queryByText("Competitor")).not.toBeInTheDocument();
  await userEvent.click(within(ours).getByRole("button", { name: "Edit" }));
  expect(within(ours).getByRole("combobox", { name: /Product/ })).toBeInTheDocument();
  await userEvent.click(within(ours).getByRole("checkbox", { name: /A competitor’s product/ }));
  expect(within(ours).queryByRole("combobox", { name: /Product/ })).not.toBeInTheDocument();
  const words = within(ours).getByRole("textbox", { name: /What it shows/ });
  expect(words).toHaveValue(""); // its old words may name the brand's product: written again
  await userEvent.type(words, "A rival's alarm.");
  await userEvent.click(within(ours).getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /brands/1/footage/10")?.body).toEqual({ description: "A rival's alarm.", product_id: null, no_product: true, competitor: true }));
});

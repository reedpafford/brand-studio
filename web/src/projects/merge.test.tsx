import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test, vi } from "vitest";
import { MaybeSame, MaybeSameBadge } from "./MaybeSame";
import { linesText, mergedText, MergeRole, type MergeAdapter, type Moved } from "./MergeRole";
import { setViewport } from "../test/viewport";

const moved: Moved = { shots: ["1.2", "2.1", "3.4"], lines: [{ version: 0, line: 4 }, { version: 0, line: 7 }, { version: 1, line: 4 }, { version: 1, line: 6 }, { version: 1, line: 9 }], look_unused: { name: "His friend with the supercar" } };
const others = [
  { id: 1, role: "Kimchi", kind: "Helper", locked: true, facts: "Late 20s · man" },
  { id: 2, role: "Nate", kind: "Main", locked: false, facts: "Early 30s · man" },
];

function open(adapter: Partial<MergeAdapter> = {}, extra: Partial<Parameters<typeof MergeRole>[0]> = {}) {
  const a: MergeAdapter = { preview: vi.fn(async () => moved), merge: vi.fn(async () => moved), ...adapter };
  const onMerged = vi.fn();
  const onClose = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MergeRole role="His friend with the supercar" roleId={3} others={others} adapter={a} onMerged={onMerged} onClose={onClose} {...extra} />
    </QueryClientProvider>,
  );
  return { a, onMerged, onClose };
}

test("lines read as 'A lines 4 and 7, B lines 4, 6 and 9' and the toast text counts shots and lines", () => {
  expect(linesText(moved.lines)).toBe("A lines 4 and 7, B lines 4, 6 and 9");
  expect(mergedText("Kimchi", moved)).toBe("Merged into Kimchi. 3 shots and 5 lines moved.");
  expect(mergedText("Kimchi", { shots: [], lines: [{ version: 0, line: 1 }], look_unused: null })).toBe("Merged into Kimchi. 1 line moved.");
  expect(mergedText("Kimchi", { shots: ["1.1"], lines: [], look_unused: null })).toBe("Merged into Kimchi. 1 shot moved.");
  expect(mergedText("Kimchi", { shots: [], lines: [], look_unused: null })).toBe("Merged into Kimchi.");
  expect(mergedText("Kimchi", { shots: ["1.1"], lines: [{ version: 0, line: 1 }], look_unused: null })).toBe("Merged into Kimchi. 1 shot and 1 line moved.");
});

test("nothing is picked at first: Merge waits, and picking a role shows what moves and merges free", async () => {
  setViewport(1440);
  const { a, onMerged } = open();
  expect(screen.getByText("Merge His friend with the supercar into…")).toBeInTheDocument();
  const merge = screen.getByRole("button", { name: /^Merge · Free/ });
  expect(merge).toBeDisabled();
  expect(merge).toHaveAccessibleDescription("Pick who this is the same person as");
  expect(screen.getByText("Locked")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("radio", { name: /Kimchi/ }));
  const what = await screen.findByLabelText("What moves to Kimchi");
  expect(within(what).getByText("3 shots: 1.2, 2.1, 3.4")).toBeInTheDocument();
  expect(within(what).getByText(/A lines 4 and 7, B lines 4, 6 and 9/)).toBeInTheDocument();
  expect(within(what).getByText("The words stay exactly as written; only who says them changes.")).toBeInTheDocument();
  expect(within(what).getByText("Kimchi keeps Kimchi's look.")).toBeInTheDocument(); // the picked role is locked
  await userEvent.click(screen.getByRole("button", { name: /^Merge · Free/ }));
  expect(a.merge).toHaveBeenCalledWith(1);
  expect(onMerged).toHaveBeenCalledWith(others[0], moved);
});

test("an unlocked target says the merged role's look isn't used any more, but isn't deleted", async () => {
  setViewport(1440);
  open();
  await userEvent.click(screen.getByRole("radio", { name: /Nate/ }));
  expect(await screen.findByText("The look made for His friend with the supercar isn't used any more, but it isn't deleted.")).toBeInTheDocument();
});

test("a suggested role starts picked, a video merge says it changes this video only, and a refusal shows in words", async () => {
  setViewport(1440);
  open({ merge: vi.fn(async () => { throw new Error("They're from another script."); }) }, { suggested: 1, videoOnly: true });
  expect(screen.getByText("This changes this video only.")).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: /Kimchi/ })).toBeChecked();
  await userEvent.click(screen.getByRole("button", { name: /^Merge · Free/ }));
  expect(await screen.findByText("They're from another script.")).toBeInTheDocument();
});

test("on a phone it is a sheet with 44px rows", async () => {
  setViewport(390);
  open();
  expect(screen.getByRole("dialog", { name: "Merge His friend with the supercar into…" })).toBeInTheDocument();
  expect(screen.getAllByRole("radio")[0].closest("label")!.className).toContain("min-h-11");
});

const pair = (a: number, b: number) => ({ a, b, into: a, why: `Both are described as Nate's friend (${a}${b}).` });
const name = (id: number) => `Role ${id}`;

test("each pair gets a note with its reason, Merge and They're different; the cap is three, the rest wait under a disclosure", async () => {
  const onMerge = vi.fn();
  const onDismiss = vi.fn();
  render(<MaybeSame pairs={[pair(1, 2), pair(3, 4), pair(5, 6), pair(7, 8), pair(9, 10)]} name={name} onMerge={onMerge} onDismiss={onDismiss} />);
  expect(screen.getAllByText(/^These may be the same person:/)).toHaveLength(5); // the extra two are in the closed disclosure
  const details = screen.getByText("2 more pairs may be the same person").closest("details")!;
  expect(details.open).toBe(false);
  expect(screen.getByText("Both are described as Nate's friend (12).")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Merge Role 1 and Role 2" }));
  expect(onMerge).toHaveBeenCalledWith(pair(1, 2));
  await userEvent.click(screen.getByRole("button", { name: "Role 1 and Role 2 are different" }));
  expect(onDismiss).toHaveBeenCalledWith(pair(1, 2));
});

test("no pairs, nothing shown", () => {
  const { container } = render(<MaybeSame pairs={[]} name={name} onMerge={() => {}} onDismiss={() => {}} />);
  expect(container).toBeEmptyDOMElement();
});

test("the 'May be the same as' badge is a 44px tap target on a phone", () => {
  render(<MaybeSameBadge other="Kimchi" onClick={() => {}} />);
  expect(screen.getByRole("button", { name: "May be the same as Kimchi" }).className).toContain("min-h-11");
});

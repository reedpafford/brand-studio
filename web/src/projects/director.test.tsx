import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { ToastProvider } from "../toast";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { DirectorPanel } from "./DirectorPanel";

const owner = { id: 1, email: "o@b.co", name: "Olu", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, role: "editor" };
const at = new Date().toISOString();
const turn = (n: number, o: object = {}) => ({ turn: n, tool: "storyboard", why: "The looks are approved, so the storyboard comes next.", result: "Making the storyboard.", status: "succeeded", created_at: at, ...o });
const run = (o: object = {}) => ({ status: "running", ended: "", turns: [turn(1, { tool: "plan", result: "Making the shots.", why: "There are no shots yet." }), turn(2)], spent_usd: 0.42, credits: 31, start_blocked: "The director is already building this video.", ...o });
const take = (id: number) => ({ id, number: id, file_id: id, created_at: at, verdict: "clean" });
const clips = (made: number, of: number) => Array.from({ length: of }, (_, i) => ({ id: i + 1, takes: i < made ? [take(i + 1)] : [], picked_take_id: null }));
const routes = (o: Record<string, [number, unknown]> = {}) => ({ "GET /auth/me": [200, owner] as [number, unknown], "GET /projects/9/clips": [200, []] as [number, unknown], "GET /projects/9/video": [404, { detail: "none" }] as [number, unknown], ...o });

function show(onLookInside = () => {}) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter>
          <DirectorPanel projectId={9} aspect="9:16" name="Cat buys the dip" onLookInside={onLookInside} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("at 390, an editor presses Make it and sees the progress line in credits, and each move with its reason", async () => {
  setViewport(390);
  const calls = fakeServer(routes({ "GET /auth/me": [200, editor], "GET /projects/9/director": [200, run({ status: "none", turns: [], credits: 0, spent_usd: null, start_blocked: "" })], "POST /projects/9/director": [201, run({ spent_usd: null })] }));
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Make it" }));
  expect(calls.some((c) => c.key === "POST /projects/9/director")).toBe(true);
  expect(await screen.findByText("Making the storyboard · up to 31 credits so far · you can leave this page")).toBeInTheDocument();
  expect(screen.getByText("Making the shots.")).toBeInTheDocument();
  expect(screen.getByText("The looks are approved, so the storyboard comes next.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$|ask (Reed|the owner)/i);
});

test("making clips, the line counts them: Making clips: 6 of 9", async () => {
  fakeServer(routes({ "GET /projects/9/clips": [200, clips(6, 9)], "GET /projects/9/director": [200, run({ spent_usd: null, credits: 42, turns: [turn(1, { tool: "make_take", result: "Making 9 takes." })] })] }));
  show();
  expect(await screen.findByText("Making clips: 6 of 9 · up to 42 credits so far · you can leave this page")).toBeInTheDocument();
});

test("Make it is disabled with the server's plain reason when the script isn't published", async () => {
  fakeServer(routes({ "GET /projects/9/director": [200, run({ status: "none", turns: [], start_blocked: "The director builds from a published script. Publish it first." })] }));
  show();
  expect(await screen.findByRole("button", { name: "Make it" })).toBeDisabled();
  expect(screen.getByText("The director builds from a published script. Publish it first.")).toBeInTheDocument();
});

test("the owner sees the director's own time in dollars; even if the server sent it, an editor never does", async () => {
  setViewport(1440);
  fakeServer(routes({ "GET /projects/9/director": [200, run()] }));
  show();
  expect(await screen.findByText(/up to 31 credits so far · the director's own time \$0\.42/)).toBeInTheDocument();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  fakeServer(routes({ "GET /auth/me": [200, editor], "GET /projects/9/director": [200, run()] }));
  show();
  expect(await screen.findByText(/up to 31 credits so far/)).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("$");
});

test("a held move says Waiting for approval", async () => {
  fakeServer(routes({ "GET /projects/9/director": [200, run({ turns: [turn(1), turn(2, { tool: null, why: "", result: "", status: "needs_owner_approval" })] })] }));
  show();
  expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
  expect(screen.getByText(/^Waiting for the owner's OK · up to 31 credits/)).toBeInTheDocument();
});

test("Stop asks first, says what still finishes, and stops the run", async () => {
  const calls = fakeServer(routes({ "GET /projects/9/director": [200, run()], "POST /projects/9/director/stop": [200, run({ status: "ended", ended: "Stopped.", start_blocked: "" })] }));
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Stop" }));
  expect(screen.getByText(/What it already started still finishes, and nothing is undone/)).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Stop" }).at(-1)!);
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/director/stop")).toBe(true));
  expect(await screen.findByText(/^Stopped\. · 31 credits for this run/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make it again" })).toBeEnabled();
});

test("at 390, the delivered cut plays and downloads, with the total, the note, what it redid and why, and Look inside", async () => {
  setViewport(390);
  const done = run({
    status: "delivered",
    start_blocked: "",
    credits: 58,
    spent_usd: null,
    turns: [
      turn(1, { tool: "make_take", result: "Making 3 takes.", why: "Every clip needs a take." }),
      turn(2, { tool: "make_take", result: "Making 1 take.", why: "Take 1 of c3 is flagged: the label is hard to read." }),
      turn(3, { tool: "deliver", why: "Every take checked clean; take 2 of clip 3 has the clearest product shot.", result: "Delivered." }),
    ],
  });
  const inside = vi.fn();
  fakeServer(routes({ "GET /auth/me": [200, editor], "GET /projects/9/director": [200, done], "GET /projects/9/video": [200, { id: 3, file_id: 77, song_take_id: null, narration: null, created_at: at }] }));
  show(inside);
  expect(await screen.findByLabelText("The finished video")).toBeInTheDocument();
  expect(screen.getByText("Delivered")).toBeInTheDocument();
  expect(screen.getAllByText("Every take checked clean; take 2 of clip 3 has the clearest product shot.")[0]).toBeVisible(); // the note, and again in Every move
  expect(screen.getByText("58 credits for this run")).toBeInTheDocument();
  await userEvent.click(screen.getByText("What it redid (1)"));
  expect(screen.getAllByText("Take 1 of c3 is flagged: the label is hard to read.")[0]).toBeVisible();
  expect(screen.getByRole("link", { name: /Download MP4/ })).toHaveAttribute("download", "cat-buys-the-dip.mp4");
  await userEvent.click(screen.getByRole("button", { name: "Look inside" }));
  expect(inside).toHaveBeenCalled();
  expect(document.body.textContent).not.toContain("$");
});

test("while it runs, only the newest 5 moves show, and Show all opens the rest", async () => {
  setViewport(390);
  fakeServer(routes({ "GET /projects/9/director": [200, run({ turns: Array.from({ length: 8 }, (_, i) => turn(i + 1, { result: `Move ${i + 1}.` })) })] }));
  show();
  expect(await screen.findByText("Move 8.")).toBeInTheDocument();
  expect(screen.queryByText("Move 3.")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Show all 8 moves" }));
  expect(screen.getByText("Move 1.")).toBeInTheDocument();
});

import { afterEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CutEditor } from "./CutEditor";
import { cutOut } from "../test/cut";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

afterEach(() => vi.unstubAllGlobals());

const swaps = [
  { take_id: 102, file_id: 202, poster_file_id: 302, label: "In the cut", kind: "in_cut" },
  { take_id: 7, file_id: 207, poster_file_id: null, label: "Take 1", kind: "take" },
  { take_id: 104, file_id: 204, poster_file_id: 304, label: "Clip 4", kind: "clip" },
  { take_id: 900, file_id: 990, poster_file_id: null, label: "Library", kind: "library" },
];

function open(cut: ReturnType<typeof cutOut>, extra: Record<string, [number, unknown]> = {}) {
  const calls = fakeServer({
    "GET /projects/9/cut": [200, cut],
    "GET /projects/9/cut/swaps/c1": [200, swaps],
    "GET /projects/9/cut/swaps/c2": [200, swaps],
    "GET /projects/9/clips": [200, [{ id: 42, clip_id: "c2" }]],
    ...extra,
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CutEditor projectId={9} aspect="9:16" projectName="Beer gut doctor rant" />
    </QueryClientProvider>,
  );
  return calls;
}

test("S7-01: the cut plays with its words, the piece under the playhead and five tracks; Download MP4 when nothing's waiting", async () => {
  setViewport(1440);
  open(cutOut());
  const box = await screen.findByLabelText("Cut editor");
  expect(within(box).getByRole("heading", { name: "Cut 2" })).toBeInTheDocument();
  expect(within(box).getByText("0:12 · 3 clips")).toBeInTheDocument();
  expect(within(box).getByRole("link", { name: /Download MP4/ })).toHaveAttribute("download", "Beer gut doctor rant.mp4");
  const piece = within(box).getByRole("region", { name: "B-roll, clip 1" });
  expect(within(piece).getByText("0:00.0 – 0:04.0 · 4.0 s")).toBeInTheDocument();
  expect(await within(piece).findByRole("button", { name: "Swap for Take 1" })).toBeInTheDocument();
  expect(within(piece).getByRole("button", { name: /Add sound effects · up to \$0\.01/ })).toBeInTheDocument();
  expect(within(piece).getByText("Edits in the cut are free. New takes are made in Clips and show their price.")).toBeInTheDocument();
  const tl = within(box).getByLabelText("Timeline");
  for (const name of ["Presenter", "B-roll", "Voice", "Music", "Sound effects"]) expect(within(tl).getByText(name)).toBeInTheDocument();
  expect(within(tl).getByText(/Dr\. Pickle · bottom right/)).toBeInTheDocument();
  expect(within(tl).getByText(/Music · “Low synth bed” · much quieter under the voice/)).toBeInTheDocument();
  expect(within(tl).getByText("gurgle")).toBeInTheDocument();
  expect(within(tl).getAllByText("The director's edit")).toHaveLength(1); // its gurgle
});

test("S7-01/02: an edit is free and posts at once; the changes wait for Make the cut, and Undo all takes them back", async () => {
  setViewport(1440);
  const changed = cutOut({ changes: 2, out_of_date: true, can_undo: true });
  const calls = open(cutOut(), {
    "POST /projects/9/cut/edits": [201, changed],
    "POST /projects/9/cut/undo-all": [200, cutOut()],
    "POST /projects/9/cut": [202, { ...changed, making: { number: 3, percent: 0, doing: "laying Dr. Pickle over the B-roll", about_seconds: 40, changes: 2 } }],
  });
  await userEvent.click(await screen.findByRole("button", { name: "B-roll clip 2, 0:04 to 0:08" }));
  expect(await screen.findByText("“Every pint sits there and ferments.”")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Re-time to the words" }));
  expect(calls.find((c) => c.key === "POST /projects/9/cut/edits")?.body).toEqual({ snap: false, kind: "retime", piece: "c2" });
  expect(await screen.findByText("2 changes not in the cut yet")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Make the cut/ }));
  expect(await screen.findByText("Making Cut 3 with your 2 changes · free · about 40 s. Cut 2 keeps playing until then.")).toBeInTheDocument();
  expect(screen.getByText("Cut 3 in about 40 s")).toBeInTheDocument();
});

test("S7-02: the music sits quieter by an amount under the voice, and rises or stays down when no one speaks", async () => {
  setViewport(1440);
  const calls = open(cutOut(), { "POST /projects/9/cut/edits": [201, cutOut()] });
  await userEvent.click(await screen.findByRole("button", { name: /Music · “Low synth bed”/ }));
  const music = screen.getByRole("region", { name: "Music" });
  expect(within(music).getByText("“Low synth bed” · 0:00 – 0:12")).toBeInTheDocument();
  expect(within(music).getByText("A lot")).toBeInTheDocument();
  expect(within(music).getByText("(−18 dB)")).toBeInTheDocument();
  expect(within(music).getByRole("radio", { name: "Rise" })).toBeChecked();
  await userEvent.click(within(music).getByRole("radio", { name: "Stay down" }));
  expect(calls.find((c) => c.key === "POST /projects/9/cut/edits")?.body).toEqual({ snap: false, kind: "music", gaps: "down" });
  expect(within(music).getByRole("button", { name: "Swap the music" })).toBeInTheDocument();
  expect(within(music).getByRole("button", { name: "Remove" })).toBeInTheDocument();
});

test("S7-03: while the director edits, the banner says what it's doing and its edits carry a dot", async () => {
  setViewport(1440);
  open(cutOut({ director: { editing: true, doing: "re-timing clips 9 and 13 to the words and adding a gurgle on clip 7." } }));
  expect(
    await screen.findByText(/re-timing clips 9 and 13 to the words and adding a gurgle on clip 7\. Its edits are marked with a dot\./),
  ).toBeInTheDocument();
  expect(screen.getByText("Editing · you can watch")).toBeInTheDocument();
});

test("S7-04: the first cut being made: a waiting player, the words and a greyed timeline with its progress", async () => {
  setViewport(1440);
  open(
    cutOut({
      number: null,
      file_id: null,
      versions: [],
      making: { number: 1, percent: 70, doing: "laying Dr. Pickle over the B-roll, music under the voice", about_seconds: 20, changes: 0 },
    }),
  );
  expect(await screen.findByText("Making the cut: laying Dr. Pickle over the B-roll, music under the voice · 70%")).toBeInTheDocument();
  expect(screen.getByText("Making the cut")).toBeInTheDocument();
  expect(screen.getByText("The timeline wakes up when the first cut is ready. Every clip is already in Clips.")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Download/ })).toBeNull();
});

test("S7-06: a cut that couldn't be made says why, nothing charged, with its one-click fixes; the cut before still downloads", async () => {
  setViewport(1440);
  const why = "Cut 3 couldn't be made: the music file stops at 0:41, and the cut runs to 0:58. Nothing was charged.";
  const calls = open(cutOut({ failed: { number: 3, why, fixes: ["loop_music", "remove_music"] } }), { "POST /projects/9/cut/fix": [202, cutOut()] });
  expect(await screen.findByText(why)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Download Cut 2/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Remove the music" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Loop the music to fit · free" }));
  expect(calls.find((c) => c.key === "POST /projects/9/cut/fix")?.body).toEqual({ fix: "loop_music" });
});

test("S7-07: an editor sees credits, never dollars", async () => {
  setViewport(1440);
  open(cutOut({ sound_usd: null }));
  expect(await screen.findByRole("button", { name: /Add sound effects · under 1 credit/ })).toBeInTheDocument();
  expect(screen.queryByText(/\$/)).toBeNull();
});

test("P-12: on a phone the cut plays and lists its edits, each with Undo; the timeline is on desktop", async () => {
  setViewport(390);
  const edits = [
    { id: 1, kind: "swap", said: "Clip 7 swapped for take 1", at: 14, director: true, by: "Reed", undone: false, applies: true, in_cut: true },
    { id: 2, kind: "retime", said: "Clip 9 re-timed to the words", at: 24, director: false, by: "Reed", undone: false, applies: true, in_cut: true },
  ];
  const calls = open(cutOut({ edits }), { "POST /projects/9/cut/edits/2/undo": [200, cutOut({ edits: [edits[0]] })] });
  expect(await screen.findByText("Edits in this cut")).toBeInTheDocument();
  expect(screen.getByText("Clip 7 swapped for take 1 (the director)")).toBeInTheDocument();
  expect(screen.getByText("0:24")).toBeInTheDocument();
  expect(screen.getByText("The full timeline is on desktop. Ask the director for any edit here.")).toBeInTheDocument();
  expect(screen.queryByLabelText("Timeline")).toBeNull();
  await userEvent.click(screen.getAllByRole("button", { name: "Undo" })[1]);
  expect(calls.some((c) => c.key === "POST /projects/9/cut/edits/2/undo")).toBe(true);
});

test("Trim: an edge moves with the arrow keys and Enter keeps it; a click without moving changes nothing", async () => {
  setViewport(1440);
  const calls = open(cutOut(), { "POST /projects/9/cut/edits": [201, cutOut()] });
  await userEvent.click(await screen.findByRole("button", { name: "B-roll clip 2, 0:04 to 0:08" }));
  await userEvent.click(screen.getByRole("button", { name: "Trim" }));
  const end = screen.getByRole("slider", { name: "Trim the end" });
  await userEvent.click(end);
  expect(calls.some((c) => c.key === "POST /projects/9/cut/edits")).toBe(false);
  end.focus();
  await userEvent.keyboard("{ArrowLeft}{ArrowLeft}{Enter}");
  const sent = calls.find((c) => c.key === "POST /projects/9/cut/edits")?.body as { kind: string; piece: string; end: number };
  expect([sent.kind, sent.piece, Math.round(sent.end * 10) / 10]).toEqual(["trim", "c2", 7.8]);
});

test("Removed music stays on its track with Put it back", async () => {
  setViewport(1440);
  const base = cutOut();
  const calls = open(cutOut({ timeline: { ...base.timeline, music: { ...base.timeline.music!, removed: true } } }), {
    "POST /projects/9/cut/edits": [201, cutOut()],
  });
  await userEvent.click(await screen.findByRole("button", { name: "Put it back" }));
  expect(calls.find((c) => c.key === "POST /projects/9/cut/edits")?.body).toEqual({ snap: false, kind: "music", removed: false });
});

test("Someone who didn't make the video watches the cut, with no edit presses", async () => {
  setViewport(1440);
  open(cutOut({ can_edit: false, changes: 1, out_of_date: true }));
  expect(await screen.findByText("Whoever made this video, or the owner, edits its cut.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Re-time to the words" })).toBeNull();
  expect(screen.queryByRole("button", { name: /Make the cut/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Undo" })).toBeDisabled();
});

test("P-12: a change not in the cut can be made into the cut from the phone", async () => {
  setViewport(390);
  const calls = open(cutOut({ changes: 1, out_of_date: true }), {
    "POST /projects/9/cut": [202, cutOut({ making: { number: 3, percent: 0, doing: "", about_seconds: 20, changes: 1 } })],
  });
  await userEvent.click(await screen.findByRole("button", { name: /1 change · Make the cut/ }));
  expect(calls.some((c) => c.key === "POST /projects/9/cut")).toBe(true);
});

test("A failed cut's fixes are only for those who may edit; the Library tile opens and closes its row", async () => {
  setViewport(1440);
  const why = "Cut 3 couldn't be made: the music file stops at 0:41, and the cut runs to 0:58. Nothing was charged.";
  open(cutOut({ can_edit: false, failed: { number: 3, why, fixes: ["loop_music", "remove_music"] } }));
  expect(await screen.findByText(why)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Loop the music/ })).toBeNull();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  setViewport(1440);
  const calls = open(cutOut());
  const library = await screen.findByRole("button", { name: "Swap for one from the Library" });
  await userEvent.click(library);
  expect(library).toHaveAttribute("aria-expanded", "true");
  await userEvent.click(library);
  expect(library).toHaveAttribute("aria-expanded", "false");
  expect(calls.some((c) => c.key === "POST /projects/9/cut/edits")).toBe(false);
});

test("A refused music edit puts the slider back to the level the cut has", async () => {
  setViewport(1440);
  open(cutOut(), { "POST /projects/9/cut/edits": [422, { detail: "Quieter by 0 to 30 dB." }] });
  await userEvent.click(await screen.findByRole("button", { name: /Music · “Low synth bed”/ }));
  const slider = screen.getByRole("slider", { name: /Quieter by/ });
  fireEvent.change(slider, { target: { value: "25" } });
  expect(screen.getByText("(−25 dB)")).toBeInTheDocument();
  fireEvent.pointerUp(slider);
  expect(await screen.findByText("Quieter by 0 to 30 dB.")).toBeInTheDocument();
  expect(screen.getByText("(−18 dB)")).toBeInTheDocument();
});

test("Trim handles stay but are locked while an edit is on its way", async () => {
  setViewport(1440);
  let finish: (r: Response) => void = () => {};
  const calls = open(cutOut());
  await userEvent.click(await screen.findByRole("button", { name: "B-roll clip 2, 0:04 to 0:08" }));
  await userEvent.click(screen.getByRole("button", { name: "Trim" }));
  const real = globalThis.fetch;
  vi.stubGlobal("fetch", (input: Request) => (input.method === "POST" ? new Promise<Response>((r) => (finish = r)) : real(input)));
  await userEvent.click(screen.getByRole("button", { name: "Re-time to the words" }));
  const end = await screen.findByRole("slider", { name: "Trim the end" });
  expect(end).toHaveAttribute("aria-disabled", "true");
  end.focus();
  await userEvent.keyboard("{ArrowLeft}{Enter}");
  expect(end).toHaveAttribute("aria-valuenow", "8");
  expect(calls.filter((c) => c.key === "POST /projects/9/cut/edits")).toHaveLength(0);
  finish(new Response(JSON.stringify(cutOut()), { status: 201, headers: { "content-type": "application/json" } }));
});

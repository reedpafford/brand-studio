import type { components } from "../api/schema";

type Cut = components["schemas"]["CutOut"];
type Piece = components["schemas"]["PieceOut"];

const piece = (n: number, start: number, end: number, o: Partial<Piece> = {}): Piece => ({
  id: `c${n}`,
  clip_id: `c${n}`,
  take_id: 100 + n,
  file_id: 200 + n,
  poster_file_id: 300 + n,
  source: `Clip ${n}`,
  start,
  end,
  in_point: 0,
  said: `Line ${n}.`,
  edited: false,
  director: false,
  changed: false,
  ...o,
});

/** A delivered presenter cut, as GET …/cut answers it: three pieces, a presenter, the voice, music and one sound. */
export function cutOut(o: Partial<Cut> = {}): Cut {
  return {
    number: 2,
    file_id: 90,
    out_of_date: false,
    versions: [
      { number: 1, file_id: 80, made_at: "2026-11-03T10:20:00" },
      { number: 2, file_id: 90, made_at: "2026-11-03T10:25:00" },
    ],
    making: null,
    failed: null,
    timeline: {
      mode: "narrated",
      length: 12,
      pieces: [piece(1, 0, 4), piece(2, 4, 8, { said: "Every pint sits there and ferments." }), piece(3, 8, 12)],
      presenter: { name: "Dr. Pickle", spans: [{ start: 0, end: 12, side: "right", size: "medium", hidden: false, director: false }] },
      voice: { label: "Dr. Pickle’s voice", text: "Your gut after the weekend? Every pint sits there and ferments." },
      music: { name: "Low synth bed", file_id: 70, quieter_db: 18, gaps: "rise", loop: true, removed: false, director: false },
      words: [
        { word: "Your", start: 0.2, end: 0.5 },
        { word: "gut", start: 0.5, end: 0.9 },
        { word: "Every", start: 4.1, end: 4.4 },
        { word: "pint", start: 4.4, end: 4.8 },
      ],
      sfx: [{ piece: "c2", start: 4, end: 8, state: "ready", asked: "gurgle", how: "slight", director: true }],
      speed: 1,
      captions: false,
      cards: true,
    },
    edits: [],
    changes: 0,
    can_undo: false,
    can_redo: false,
    going: [],
    director: { editing: false, doing: "" },
    can_edit: true,
    sound_credits: 0.06,
    sound_usd: 0.006,
    ...o,
  };
}

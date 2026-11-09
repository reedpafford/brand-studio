import { act } from "@testing-library/react";
import { vi } from "vitest";

/** The browser's stream of a video's changes (videos/live.ts), stood in for: the test says when it opens, speaks or drops. */
export class FakeSource {
  static all: FakeSource[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeSource.all.push(this);
  }
  addEventListener() {}
  close() {
    this.closed = true;
  }
}

/** Put the stand-in in the browser's place (vi.unstubAllGlobals takes it out). */
export function fakeStream() {
  FakeSource.all = [];
  vi.stubGlobal("EventSource", FakeSource);
}

/** The server tells every open page that `kind` changed ("jobs", "made", "cards", "video"). */
export const tell = (kind: string) => act(() => FakeSource.all.filter((s) => !s.closed).forEach((s) => s.onmessage?.({ data: kind })));

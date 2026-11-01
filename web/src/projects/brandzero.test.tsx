import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { useBrandPieces } from "../clip/BrandPieces";
import { useScreens } from "../brand/screens";
import { useBriefChoices } from "./BriefPickers";

afterEach(() => vi.unstubAllGlobals());
const wrap = ({ children }: { children: ReactNode }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;

test("before the brand loads (brand 0), nothing asks for /brands/0/screens; once it has, the screens are read (QA sweep)", async () => {
  const calls = fakeServer({ "GET /brands/3/screens": [200, []], "GET /library/character": [200, []], "GET /library/place": [200, []], "GET /library/prop": [200, []] });
  const { rerender } = renderHook(({ id }) => [useBriefChoices(id, {}), useBrandPieces(id), useScreens(id)], { wrapper: wrap, initialProps: { id: 0 } });
  await new Promise((r) => setTimeout(r, 20));
  expect(calls.filter((c) => c.key.startsWith("GET /brands/0"))).toEqual([]);
  rerender({ id: 3 });
  await waitFor(() => expect(calls.some((c) => c.key === "GET /brands/3/screens")).toBe(true));
  expect(calls.filter((c) => c.key.startsWith("GET /brands/0"))).toEqual([]);
});

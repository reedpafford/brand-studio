export const KINDS = {
  characters: { kind: "character", one: "character", title: "Characters" },
  places: { kind: "place", one: "place", title: "Places" },
  props: { kind: "prop", one: "prop", title: "Props" },
} as const;

export type KindSlug = keyof typeof KINDS;
export const isKindSlug = (s: string | undefined): s is KindSlug => !!s && s in KINDS;

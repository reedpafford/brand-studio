export const KINDS = {
  characters: { kind: "character", one: "character", them: "them", title: "Characters" },
  places: { kind: "place", one: "place", them: "it", title: "Places" },
  props: { kind: "prop", one: "prop", them: "it", title: "Props" },
} as const;

type KindSlug = keyof typeof KINDS;
export const isKindSlug = (s: string | undefined): s is KindSlug => !!s && s in KINDS;

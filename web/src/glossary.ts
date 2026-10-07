// Plain-language definitions of every term the site uses. Each one restates a rule the pipeline
// applies (docs/architecture/REVAMP_PLAN_V3.md, contracts/descriptions.py); the numbers come from
// METHOD, which tests/test_web_method.py checks against config/pipeline.yaml.

/** Thresholds quoted in the explanations; must equal config/pipeline.yaml (tests/test_web_method.py). */
export const METHOD = {
  strongShare: 0.9, // identity.strong
  coreShare: 0.5, // identity.core
  nameRetainedShare: 0.15, // identity.name_retained
  growthMinShare: 0.15, // identity.growth_min_h
  displacementWidthKm: 1.0, // overlay.displacement_width_km
  sliverKm2: 0.5, // overlay.sliver_abs_km2
} as const;

export type TermKey = keyof typeof GLOSSARY;

export const GLOSSARY = {
  identity: {
    term: "District identity",
    text: "One district followed across the maps. It keeps the same identity, and the same key, as long as its core land carries on, even when its name or state changes.",
  },
  key: {
    term: "Key",
    text: "A permanent ID such as IND-000202 for one district identity. Names change; keys do not.",
  },
  map: {
    term: "Map",
    text: "One of nine boundary maps: census-era maps for 1951 to 2021, and the Survey of India map of 2025. Boundaries are only known on these dates; nothing between them is guessed.",
  },
  window: {
    term: "Window",
    text: "The span between two consecutive maps, such as 1971 to 1981. A change seen in a window happened somewhere inside it.",
  },
  carved: {
    term: "Carved out",
    text: "A new district made from part of another district, which itself carried on.",
  },
  split: {
    term: "Split",
    text: "A district whose land went into new districts and which did not carry on itself.",
  },
  merged: {
    term: "Merged",
    text: "Two or more districts that ended and whose land formed a new district together.",
  },
  restored: {
    term: "Restored",
    text: "A district that reappears after being absorbed into another. It gets a new identity, linked back to the old one.",
  },
  transfer: {
    term: "Transfer",
    text: "Land that moved between two districts that both carried on, such as a few villages changing district.",
  },
  measured: {
    term: "Measured",
    text: "The event's area is exact: it was the only recorded event touching those districts between two maps, so the land that moved belongs to it alone.",
  },
  bounded: {
    term: "Bounded",
    text: "Two or more events touched the same districts between two maps. Only their combined area is known, which is an upper limit for each one.",
  },
  notMeasurable: {
    term: "Not measurable",
    text: "The district the events list names as the parent could not be found on the maps, so no area can be attached to the event.",
  },
  event: {
    term: "Administrative event",
    text: "A change recorded in the events compilation: a district created, split or renamed, with a year. Events confirm what the maps show; they never override them.",
  },
  crosswalk: {
    term: "Crosswalk",
    text: "How much of a past district's land lies inside each 2025 district. These shares are the weights for restating old statistics on today's districts.",
  },
  coverage: {
    term: "Coverage",
    text: "The share of a 2025 district's land that is covered by districts that reported a value. Below 100% means part of it had no data; nothing is filled in.",
  },
  displacement: {
    term: "Boundary displacement",
    text: `Thin strips, under ${METHOD.displacementWidthKm} km wide, where two maps draw the same border slightly differently. They count as a drawing difference, not as land changing hands.`,
  },
  question: {
    term: "Open question",
    text: "A place where the maps and the events list disagree. It is recorded, never corrected automatically, and closes only when someone adds documentary evidence.",
  },
  reference: {
    term: "The 2025 map",
    text: "The Survey of India map of 2025, onto which statistics are restated. It does not yet show Andhra Pradesh's 2022 or Rajasthan's 2023 new districts, or Mizoram's 2019 ones.",
  },
} as const;

/** Plain names for the pipeline's relationship codes. */
export const RELATION = {
  FORMED_FROM: { verb: "carved out of", noun: "carved out", term: "carved" },
  SPLIT_FROM: { verb: "split from", noun: "split", term: "split" },
  MERGED_INTO: { verb: "merged from", noun: "merged", term: "merged" },
  RECONSTITUTED_FROM: { verb: "restored from", noun: "restored", term: "restored" },
} as const satisfies Record<string, { verb: string; noun: string; term: TermKey }>;

export const MEASUREMENT = {
  MEASURED: { label: "Measured", term: "measured", tone: "good" },
  UNIDENTIFIED_MULTI_EVENT_WINDOW: { label: "Bounded", term: "bounded", tone: "warn" },
  NOT_MEASURABLE: { label: "Not measurable", term: "notMeasurable", tone: "" },
} as const satisfies Record<string, { label: string; term: TermKey; tone: string }>;

/** Research-queue topics, as a question a reader would ask. */
export const TOPIC = {
  EVENT_NAME_UNRESOLVED: {
    label: "Named district not on any map",
    text: "The events list names a district that no map shows under that name. Often a new district the 2025 map has not caught up with, or a spelling no rule can safely match.",
  },
  EVENT_NAME_OUTSIDE_FOOTPRINT: {
    label: "Named district outside its parent's land",
    text: "The events list says a district was formed from a parent, but on the maps that district's land never belonged to the parent. Linking them would invent a transfer the maps do not show.",
  },
  MAP_DATE: {
    label: "Map may show a later year",
    text: "Several districts appear on a map before the year the events list gives for their creation, so either the events are misdated or the map depicts later boundaries than its label.",
  },
} as const;

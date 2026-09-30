// Typed access to the read-only API. Every response is {meta, data}; meta carries the release version.

export type Meta = { pipeline_version: string; config_sha256: string; events_csv_sha256: string; reference_year: number };
type Envelope<T> = { meta: Meta; data: T };

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${res.status} ${path}: ${(await res.text()).slice(0, 200)}`);
  return ((await res.json()) as Envelope<T>).data;
}

export async function getMeta(): Promise<Meta> {
  const res = await fetch("/api/meta");
  return ((await res.json()) as Envelope<unknown>).meta;
}

export const YEARS = [1951, 1961, 1971, 1981, 1991, 2001, 2011, 2021, 2025];
export const INDIA_BOUNDS: [number, number, number, number] = [68, 6.5, 97.5, 37.2];

export type DistrictRow = {
  canonical_key: string; latest_name: string; latest_state: string;
  established_year: number; closed_year: number | null; is_active: boolean;
};
export type Registry = DistrictRow & {
  origin_kind: string; display_name: string; state_at_creation: string; n_observations: number;
  formed_after: number | null; formed_by: number; closed_after: number | null; closed_by: number | null;
  observations: { year: number; district_name: string; state: string; area_km2: number; geom_obs_id: string }[];
};
export type Edge = {
  rel_id: string; from_ck: string; to_ck: string; relationship_type: string; year_a: number; year_b: number;
  period_start: number; period_end: number; transfer_km2: number; outflow_share: number; inflow_share: number;
  depth: number; from_name: string; to_name: string;
};
export type Transfer = {
  transfer_id: string; from_ck: string; to_ck: string; year_a: number; year_b: number; period_start: number;
  period_end: number; transfer_km2: number; outflow_share: number; inflow_share: number; from_name: string; to_name: string;
};
export type Timeline = {
  maps: { year: number; depicted_year: number; district_name: string; state: string; area_km2: number }[];
  ledger: Record<string, number | string | boolean>[];
  transfers: Transfer[];
};
export type Parcel = GeoJSON.Feature<GeoJSON.Geometry, {
  from_ck: string; to_ck: string; from_name: string; to_name: string; transfer_km2: number; kind: string;
  row_id: string; source_table: string; direction: "in" | "out";
}>;
export type Changes = { year_a: number; year_b: number; type: "FeatureCollection"; features: Parcel[] };
export type Claim = { claim_type: string; verdict: string; reason: string; our_value: string | null; value: string; citation: string; claim_id: string };
export type QueueItem = { queue_item_id: string; topic: string; ref: string; subject: string; state: string | null; detail: string; status: string; finding_id: string | null };
export type EventRow = {
  event_id: string; event_type: string; recorded_as: string; event_state: string; parent_district_raw: string;
  effective_year: number; n_predecessors: number; n_successors: number; measurement_status: string;
};
export type CrosswalkRow = {
  year: number; source_ck: string; target_ck: string; area_km2: number; share_of_source: number; share_of_target: number;
  target_name?: string; target_state?: string; source_name?: string; source_state?: string;
};
export type Overview = {
  maps: { year: number; districts: number; mapped_km2: number; new_identities: number }[];
  lineage: { year: number; relationship_type: string; edges: number; km2: number }[];
  transfers: { year: number; transfers: number; km2: number }[];
  events: { decade: number; status: string; events: number }[];
  identities: { total: number; active: number; closed: number };
  evidence: { claim_type: string; verdict: string; n: number }[];
  research_open: { topic: string; n: number }[];
};
export type Check = { check_id: string; severity: string; n_violations: number; description: string; detail: string | null };
export type DictionaryEntry = { table: string; column: string; dtype: string; nullable: boolean; unit: string; allowed: string; meaning: string; source_stage: string };

export const fmt = (n: number | null | undefined, digits = 0) =>
  n == null ? "–" : n.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
export const km2 = (n: number | null | undefined) => (n == null ? "–" : `${fmt(n)} km²`);
export const pct = (n: number | null | undefined, digits = 0) => (n == null ? "–" : `${(n * 100).toFixed(digits)}%`);

export function bbox(geom: GeoJSON.Geometry): [number, number, number, number] {
  let [x0, y0, x1, y1] = [180, 90, -180, -90];
  const walk = (c: unknown): void => {
    if (typeof (c as number[])[0] === "number") {
      const [x, y] = c as number[];
      x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
    } else (c as unknown[]).forEach(walk);
  };
  if ("coordinates" in geom) walk(geom.coordinates);
  return [x0, y0, x1, y1];
}

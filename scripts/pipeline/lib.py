"""Shared library for the District Evolution pipeline (v3).

Paths, configuration, the one area method, deterministic IDs, name/state
normalization, reference tables, and the validated table writer. Every
threshold lives in config/pipeline.yaml and is read through CFG.
"""

from __future__ import annotations

import functools
import hashlib
import re
import unicodedata
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import yaml
from pyproj import Geod

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
SILVER_GEOM_DIR = PROJECT_ROOT / "data" / "silver" / "geometry"
GOLD_SPATIAL_DIR = PROJECT_ROOT / "data" / "gold" / "spatial"
GOLD_EVENTS_DIR = PROJECT_ROOT / "data" / "gold" / "events"
GOLD_CORE_DIR = PROJECT_ROOT / "data" / "gold" / "core"
PRODUCTS_DIR = PROJECT_ROOT / "data" / "products"
WAREHOUSE_PATH = PROJECT_ROOT / "data" / "gold" / "district_evolution.duckdb"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "pipeline"
EVENTS_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "events"
EVENTS_CSV = PROJECT_ROOT / "data" / "bronze" / "events" / "district_evolution_master.csv"

for _d in (SILVER_GEOM_DIR, GOLD_SPATIAL_DIR, GOLD_EVENTS_DIR, GOLD_CORE_DIR,
           PRODUCTS_DIR, OUTPUT_DIR, EVENTS_OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

with open(CONFIG_DIR / "pipeline.yaml") as _fh:
    CFG: dict = yaml.safe_load(_fh)

PIPELINE_VERSION: str = CFG["pipeline_version"]
VINTAGES: list[tuple[str, int]] = [(s, int(y)) for s, y in CFG["vintages"]]
YEARS: list[int] = [y for _, y in VINTAGES]
SOURCE_BY_YEAR: dict[int, str] = {y: s for s, y in VINTAGES}
REFERENCE_YEAR: int = int(CFG["reference_year"])
WINDOWS: list[tuple[int, int]] = list(zip(YEARS[:-1], YEARS[1:]))


def silver_path(year: int) -> Path:
    return SILVER_GEOM_DIR / f"{SOURCE_BY_YEAR[year]}_{year}.geoparquet"


# ---------------------------------------------------------------------------
# Area
# ---------------------------------------------------------------------------

GEOD = Geod(ellps="WGS84")


def geodesic_area_perimeter(geom) -> tuple[float, float]:
    """(area km2, perimeter km) on the WGS84 ellipsoid. The one area method."""
    if geom is None or geom.is_empty:
        return 0.0, 0.0
    area_m2, perim_m = GEOD.geometry_area_perimeter(geom)
    return abs(float(area_m2)) / 1e6, float(perim_m) / 1e3


def geodesic_area_km2(geom) -> float:
    return geodesic_area_perimeter(geom)[0]


def sliver_threshold_km2(area_a: float, area_b: float) -> float:
    ov = CFG["overlay"]
    smaller = min(area_a, area_b)
    return max(ov["sliver_abs_km2"], smaller * ov["sliver_rel_fraction"])


def within_closure(error_km2, area_km2):
    tol = np.maximum(CFG["closure"]["tol_km2"], np.asarray(area_km2) * CFG["closure"]["tol_pct"] / 100.0)
    return np.abs(error_km2) <= tol


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

def stable_id(*parts: object) -> str:
    """Deterministic identifier: sha256 of a natural key. Reruns are idempotent."""
    text = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[.’'`,()]")
_SEP_RE = re.compile(r"[-–—/_]")


def normalize_name(value: object) -> str:
    """Matching key for a district or state name. Not a display value."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower().replace("&", " and ")
    text = _PUNCT_RE.sub("", text)
    text = _SEP_RE.sub(" ", text)
    text = re.sub(r"\bdistrict\b", " ", text)
    return _WS_RE.sub(" ", text).strip()


def display_name(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return _WS_RE.sub(" ", str(value).replace("_", " ")).strip().title()


# Census 2011 state codes, used only for the 2011 Stanford layer.
PC11_STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman and Diu", "26": "Dadra and Nagar Haveli", "27": "Maharashtra",
    "28": "Andhra Pradesh", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep",
    "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
}

# Pure spelling / rename drift of one state name (1:1). One-to-many historical
# reorganisations live in data/reference/state_lineage.csv instead.
STATE_SPELLINGS = {
    "orissa": "Odisha", "pondicherry": "Puducherry", "uttranchal": "Uttarakhand",
    "uttaranchal": "Uttarakhand", "karnatak": "Karnataka",
    "andamans and nicobars": "Andaman and Nicobar Islands",
    "andaman and nicobar": "Andaman and Nicobar Islands",
    "andaman and nicobar island": "Andaman and Nicobar Islands",
    "tamilnadu": "Tamil Nadu", "laccadive minicoy and amindiv": "Lakshadweep",
    "laccadive minicoy and amindivi islands": "Lakshadweep",
    "dadra and nagar have": "Dadra and Nagar Haveli",
    "andhra pradesh telangana": "Andhra Pradesh",
    "travancore cochin": "Travancore Cochin", "p e p s u": "Pepsu",
    "delhi": "Delhi", "nct of delhi": "Delhi",
}


def canonical_state(value: object) -> str:
    norm = normalize_name(value)
    return STATE_SPELLINGS.get(norm) or display_name(norm)


def parse_multi_name(value: object) -> list[str]:
    """Split a comma/'and'-joined list of district names (events CSV parent_district)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = re.sub(r"\band\b", ",", str(value).strip(), flags=re.IGNORECASE)
    return [p for p in (x.strip().rstrip(".").strip() for x in text.split(",")) if p]


def jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    l1, l2 = len(s1), len(s2)
    md = max(max(l1, l2) // 2 - 1, 0)
    m1, m2 = [False] * l1, [False] * l2
    matches = 0
    for i in range(l1):
        for j in range(max(0, i - md), min(i + md + 1, l2)):
            if not m2[j] and s1[i] == s2[j]:
                m1[i] = m2[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    t = k = 0
    for i in range(l1):
        if m1[i]:
            while not m2[k]:
                k += 1
            t += s1[i] != s2[k]
            k += 1
    jaro = (matches / l1 + matches / l2 + (matches - t / 2) / matches) / 3.0
    prefix = next((i for i, (a, b) in enumerate(zip(s1[:4], s2[:4])) if a != b), min(4, l1, l2))
    return jaro + prefix * p * (1.0 - jaro)


# ---------------------------------------------------------------------------
# Reference tables
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def state_lineage_graph() -> nx.DiGraph:
    ref = pd.read_csv(REFERENCE_DIR / "state_lineage.csv")
    g = nx.DiGraph()
    for _, r in ref.iterrows():
        g.add_edge(normalize_name(r["parent_state"]), normalize_name(r["child_state"]))
    return g


@functools.lru_cache(maxsize=4096)
def compatible_states(state_norm: str) -> frozenset[str]:
    """States a district recorded under `state_norm` may appear under at another
    date: itself, its ancestors and descendants in the reorganisation graph, and
    its siblings (states sharing a direct parent, e.g. Tamil Nadu / Andhra Pradesh
    via Madras)."""
    g = state_lineage_graph()
    out = {state_norm}
    if state_norm in g:
        out |= nx.ancestors(g, state_norm) | nx.descendants(g, state_norm)
        for parent in g.predecessors(state_norm):
            out |= set(g.successors(parent))
    return frozenset(out)


@functools.lru_cache(maxsize=1)
def _depiction() -> dict[tuple[str, int], int]:
    ref = pd.read_csv(REFERENCE_DIR / "vintage_depiction.csv")
    ref = ref[ref.status == "CONFIRMED"]
    return {(normalize_name(canonical_state(s)), int(v)): int(d)
            for s, v, d in zip(ref.state, ref.vintage, ref.depicted_year)}


def depicted_year(state: str, vintage: int) -> int:
    """The year a map layer's boundaries actually depict for a state. Equals the
    vintage label unless data/reference/vintage_depiction.csv confirms otherwise
    (e.g. the Stanford "1981" Assam layer depicts ~1989 boundaries)."""
    return _depiction().get((normalize_name(canonical_state(state)), int(vintage)), int(vintage))


@functools.lru_cache(maxsize=1)
def known_geometry_gaps() -> pd.DataFrame:
    """Vintages confirmed to be missing districts that other evidence (events
    compilation, Wikidata) says already existed by that map's label year. Unlike
    vintage_depiction.csv this never touches depicted_year: a gap here is the map
    lagging its own label (SOI 2025 still showing Mizoram's pre-2018 8 districts),
    not the map's label being an early alias for a later, internally consistent
    boundary set. Forcing a lag into depicted_year would invert vintage ordering
    (s11 CHECK depicted_year >= year; s09 assumes d(a) < event_year <= d(b))."""
    ref = pd.read_csv(REFERENCE_DIR / "known_geometry_gaps.csv")
    return ref[ref.status == "CONFIRMED"]


def is_documented_geometry_gap(state: str, vintage: int) -> bool:
    gaps = known_geometry_gaps()
    key = (normalize_name(canonical_state(state)), int(vintage))
    documented = {(normalize_name(canonical_state(s)), int(v)) for s, v in zip(gaps.state, gaps.vintage)}
    return key in documented


def shown_before_creation(registry: pd.DataFrame) -> pd.DataFrame:
    """New districts whose first map is labelled earlier than their creation year in
    the events compilation (a source independent of the maps). A state-map with
    many of these depicts later boundaries than its label says."""
    ev = pd.read_csv(EVENTS_CSV)

    def key(name, state):
        return alias_key(normalize_name(name)), normalize_name(canonical_state(state))
    first = ev.assign(k=[key(n, s) for n, s in zip(ev.child_district, ev.state)]).groupby("k").effective_year.min()
    new = registry[registry.origin_kind == "NEW"]
    out = pd.DataFrame({"canonical_key": new.canonical_key, "latest_name": new.latest_name,
                        "state": new.latest_state, "first_map": new.established_year,
                        "csv_year": [first.get(key(n, s)) for n, s in zip(new.latest_name, new.latest_state)]})
    out = out[out.csv_year.notna()]
    out["depicted"] = [depicted_year(s, y) for s, y in zip(out.state, out.first_map)]
    out["shown_before_creation"] = out.csv_year > out.depicted
    return out


@functools.lru_cache(maxsize=1)
def name_aliases() -> pd.DataFrame:
    df = pd.read_csv(REFERENCE_DIR / "name_aliases.csv")
    df["alias_norm"] = df["alias_name"].map(normalize_name)
    df["canonical_norm"] = df["canonical_name"].map(normalize_name)
    df["state_norm"] = df["state"].map(lambda s: normalize_name(canonical_state(s)))
    return df


@functools.lru_cache(maxsize=1)
def _alias_map() -> dict[str, str]:
    a = name_aliases()
    return dict(zip(a["alias_norm"], a["canonical_norm"]))


def alias_key(name_norm: str) -> str:
    """Canonical rename/spelling key: the alias target if `name_norm` is a
    known alias, else the name itself."""
    return _alias_map().get(name_norm, name_norm)


@functools.lru_cache(maxsize=1)
def _alias_pairs() -> frozenset[tuple[str, str]]:
    a = name_aliases()
    pairs = set(zip(a["alias_norm"], a["canonical_norm"])) | set(zip(a["canonical_norm"], a["alias_norm"]))
    # aliases sharing a canonical name are aliases of each other
    for _, grp in a.groupby("canonical_norm"):
        names = list(grp["alias_norm"])
        pairs |= {(x, y) for x in names for y in names}
    return frozenset(pairs)


def _token_sort(s: str) -> str:
    return " ".join(sorted(s.split()))


def name_similarity(a_norm: str, b_norm: str) -> float:
    """Best Jaro-Winkler over raw, alias-canonical, and word-order-insensitive forms."""
    if not a_norm or not b_norm:
        return 0.0
    ka, kb = alias_key(a_norm), alias_key(b_norm)
    return max(jaro_winkler(a_norm, b_norm), jaro_winkler(ka, kb),
               jaro_winkler(_token_sort(ka), _token_sort(kb)))


# Directional / urban-rural qualifiers that mark a name DERIVED from a parent
# ("South 24 Parganas", "Purba Bardhaman", "Bangalore Urban"): a child named
# this way is a new district, not the parent continuing under its old name.
QUALIFIERS = frozenset({
    "north", "south", "east", "west", "central", "upper", "lower", "urban", "rural",
    "purba", "paschim", "pashchim", "pashchimi", "purbi", "uttar", "uttara", "dakshin",
    "dakshina", "madhya", "new", "greater",
})


def is_qualified_derivative(a_norm: str, b_norm: str) -> bool:
    """True when one name is the other plus directional qualifier(s)."""
    ta, tb = set(a_norm.split()), set(b_norm.split())
    qa, qb = ta & QUALIFIERS, tb & QUALIFIERS
    if qa == qb:
        return False
    ra, rb = " ".join(sorted(ta - QUALIFIERS)), " ".join(sorted(tb - QUALIFIERS))
    return bool(ra and rb) and (ra == rb or jaro_winkler(ra, rb) >= CFG["identity"]["name_jw"])


def names_agree(a_norm: str, b_norm: str) -> tuple[bool, float]:
    """(agree, similarity). Agreement = equal, documentary alias, or similarity >=
    config, unless one name is a qualified derivative of the other."""
    if not a_norm or not b_norm:
        return False, 0.0
    sim = name_similarity(a_norm, b_norm)
    if a_norm == b_norm or (a_norm, b_norm) in _alias_pairs():
        return True, sim
    return (sim >= CFG["identity"]["name_jw"] and not is_qualified_derivative(a_norm, b_norm)), sim


# ---------------------------------------------------------------------------
# Validated table I/O
# ---------------------------------------------------------------------------

def write_table(df: pd.DataFrame, path: Path, schema_name: str | None = None,
                csv_copy: Path | None = None) -> pd.DataFrame:
    """Validate against its pandera schema (if named) and write parquet (+csv)."""
    if schema_name is not None:
        import schemas  # local import: schemas imports lib
        if "geometry" in df.columns:
            schemas.validate(schema_name, pd.DataFrame(df.drop(columns="geometry")))
        else:
            df = schemas.validate(schema_name, df)
    df = df.reset_index(drop=True)
    if path.suffix == ".csv":
        df.to_csv(path, index=False)
    else:
        df.to_parquet(path, index=False)
    if csv_copy is not None:
        df.to_csv(csv_copy, index=False)
    return df

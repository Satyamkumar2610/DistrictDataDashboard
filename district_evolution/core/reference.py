"""Curated reference tables: state lineage, map depiction years, known geometry gaps."""

from __future__ import annotations

import functools

import networkx as nx
import pandas as pd

from .config import EVENTS_CSV, REFERENCE_DIR
from .names import alias_key, canonical_state, normalize_name


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

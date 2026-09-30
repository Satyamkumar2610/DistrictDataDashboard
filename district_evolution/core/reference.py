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
            for s, v, d in zip(ref.state, ref.vintage, ref.depicted_year, strict=True)}


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
    # CONFIRMED: two independent sources agree. EVENTS_ONLY rows (the events compilation and the map
    # alone) are recorded so the lag is visible (a02, docs) but explain no check until confirmed.
    return ref[ref.status == "CONFIRMED"]


def is_documented_geometry_gap(state: str, vintage: int) -> bool:
    gaps = known_geometry_gaps()
    key = (normalize_name(canonical_state(state)), int(vintage))
    documented = {(normalize_name(canonical_state(s)), int(v)) for s, v in zip(gaps.state, gaps.vintage, strict=True)}
    return key in documented


def shown_before_creation(registry: pd.DataFrame) -> pd.DataFrame:
    """New districts whose first map is labelled earlier than their creation year in
    the events compilation (a source independent of the maps). A state-map with
    many of these depicts later boundaries than its label says."""
    ev = pd.read_csv(EVENTS_CSV)

    def key(name, state):
        return alias_key(normalize_name(name)), normalize_name(canonical_state(state))
    ev["child_k"] = [key(n, s) for n, s in zip(ev.child_district, ev.state, strict=True)]
    ev["parent_k"] = [key(n, s) for n, s in zip(ev.parent_district, ev.state, strict=True)]
    # A RENAME row, or a split row whose child is the continuing parent, is not a creation:
    # the district already existed (e.g. Manipur South, 1969, renamed Churachandpur in 1981).
    renames = ev[ev.event_type == "RENAME"]
    renamed_from = dict(zip(renames.child_k, renames.parent_k, strict=True))
    created = ev[(ev.event_type != "RENAME") & (ev.child_k != ev.parent_k)].groupby("child_k").effective_year.min()

    def creation_year(k, closed):
        """Earliest creation of k or of any name it was renamed from. A creation dated at or
        after the district's closure belongs to a later homonym (Siang 1961 vs Siang 2015)."""
        years, seen = [], set()
        while k is not None and k not in seen:
            seen.add(k)
            y = created.get(k)
            if y is not None and (pd.isna(closed) or y < closed):
                years.append(y)
            k = renamed_from.get(k)
        return min(years) if years else None

    new = registry[registry.origin_kind == "NEW"]
    out = pd.DataFrame({"canonical_key": new.canonical_key, "latest_name": new.latest_name,
                        "state": new.latest_state, "first_map": new.established_year,
                        "csv_year": [creation_year(key(n, s), c) for n, s, c in
                                     zip(new.latest_name, new.latest_state, new.closed_year, strict=True)]})
    out = out[out.csv_year.notna()]
    out["depicted"] = [depicted_year(s, y) for s, y in zip(out.state, out.first_map, strict=True)]
    out["shown_before_creation"] = out.csv_year > out.depicted
    return out

"""Lineage graph helpers (networkx).

lineage_dag: nodes are CKs, edges are district_relationship rows. It must be a
DAG (architecture invariant L-1); assert_acyclic raises with the offending
cycle. ancestry lists every (descendant, ancestor, generations) pair.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd


def lineage_dag(rel: pd.DataFrame, registry: pd.DataFrame | None = None) -> nx.DiGraph:
    g = nx.DiGraph()
    if registry is not None:
        g.add_nodes_from(registry["canonical_key"])
    for r in rel.itertuples():
        g.add_edge(r.from_ck, r.to_ck, relationship_type=r.relationship_type,
                   year_a=r.year_a, year_b=r.year_b, transfer_km2=r.transfer_km2)
    return g


def assert_acyclic(g: nx.DiGraph) -> None:
    if not nx.is_directed_acyclic_graph(g):
        raise AssertionError(f"lineage graph has a cycle: {nx.find_cycle(g)}")


def ancestry(g: nx.DiGraph) -> pd.DataFrame:
    """Every (descendant, ancestor, generations) pair in the lineage DAG."""
    rows = []
    rev = g.reverse(copy=False)
    for ck in sorted(g.nodes):
        for anc, dist in nx.single_source_shortest_path_length(rev, ck).items():
            if anc != ck:
                rows.append((ck, anc, dist))
    return pd.DataFrame(rows, columns=["canonical_key", "ancestor_ck", "generations"])

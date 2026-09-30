"""Every ancestor and descendant of a district, from the release's lineage table.

    python examples/03_family_tree.py Malabar

Walks district_relationship in both directions with networkx and prints each edge with the land
that moved. The same walk backs the platform's family tree (/api/districts/{ck}/genealogy).
"""

import sys

import networkx as nx
import pandas as pd

from district_evolution import core

tables = core.RELEASE_DIR / "tables"
reg = pd.read_parquet(tables / "ck_registry.parquet").set_index("canonical_key")
rel = pd.read_parquet(tables / "district_relationship.parquet")
g = nx.from_pandas_edgelist(rel, "from_ck", "to_ck", edge_attr=True, create_using=nx.MultiDiGraph)

name = sys.argv[1] if len(sys.argv) > 1 else "Malabar"
ck = reg.index[reg.latest_name == name]
if ck.empty:
    sys.exit(f"no identity named {name}")
focus = ck[0]
family = {focus} | nx.ancestors(g, focus) | nx.descendants(g, focus)
print(f"{name} ({focus}): {len(family) - 1} relatives")
for u, v, d in sorted(g.subgraph(family).edges(data=True), key=lambda e: (e[2]["year_b"], e[0], e[1])):
    print(f"  {d['year_a']}→{d['year_b']}  {reg.latest_name[u]:>16} {d['relationship_type']:<18} {reg.latest_name[v]:<16} {d['transfer_km2']:>8,.0f} km²")

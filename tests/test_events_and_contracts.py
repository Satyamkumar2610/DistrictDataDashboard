"""Event resolution (s09), lineage graph, and data contracts."""

from types import SimpleNamespace

import networkx as nx
import pandas as pd
import pytest

from district_evolution.contracts import schemas
from district_evolution.core import lineage_graph
from district_evolution.stages import s09_event_reconciliation as s09


def data_with(cands, evidence="EXACT", bayes_factor=1000.0):
    df = pd.DataFrame(cands, columns=["name_norm", "event_state_norm", "year", "canonical_key", "match_probability"])
    df = df.assign(name_evidence=evidence, bayes_factor=bayes_factor)
    return SimpleNamespace(cand={k: g for k, g in df.groupby(["name_norm", "event_state_norm", "year"])})


def test_successor_match_is_restricted_to_the_footprint():
    d = data_with([("bilaspur", "chhattisgarh", 2001, "IND-000001", 0.94),   # same name, other state
                   ("bilaspur", "chhattisgarh", 2001, "IND-000002", 0.80)])  # the one in the footprint
    assert s09.best(d, ["bilaspur"], "chhattisgarh", 2001)[0] == "IND-000001"
    assert s09.best(d, ["bilaspur"], "chhattisgarh", 2001, allowed={"IND-000002"}, prior=0.9)[0] == "IND-000002"
    assert s09.best(d, ["bilaspur"], "chhattisgarh", 2001, allowed={"IND-000009"}, prior=0.9) is None


def test_close_runner_up_is_flagged_ambiguous():
    d = data_with([("x", "s", 1991, "IND-000001", 0.90), ("x", "s", 1991, "IND-000002", 0.85)])
    assert s09.best(d, ["x"], "s", 1991)[2] is True


def test_map_wide_link_needs_strong_name_evidence():
    # a weak spelling match (Akola ~ Kolaba) is refused map-wide, whatever its probability
    d = data_with([("kolaba", "maharashtra", 1971, "IND-000001", 0.95)], evidence="SPELLING_0.80")
    assert s09.best(d, ["kolaba"], "maharashtra", 1971) is None


def test_best_tries_every_alternative_name():
    d = data_with([("a", "s", 1991, "IND-000001", 0.60), ("b", "s", 1991, "IND-000002", 0.95)])
    assert s09.best(d, ["a", "b"], "s", 1991)[0] == "IND-000002"


def test_candidate_windows():
    assert s09.candidate_windows(1974) == [((1971, 1981), "PRIMARY"), ((1981, 1991), "LAGGED")]
    assert s09.candidate_windows(1971) == [((1961, 1971), "PRIMARY"), ((1971, 1981), "PRIMARY"),
                                           ((1981, 1991), "LAGGED")]
    assert s09.candidate_windows(1948) == []


def test_candidate_windows_use_depicted_dates():
    # the "1981" Assam map depicts ~1989: a 1983 Assam event lies between the 1971
    # map and that layer, not between the 1981 and 1991 layers
    assert s09.candidate_windows(1983, "Bihar")[0] == ((1981, 1991), "PRIMARY")
    assert s09.candidate_windows(1983, "Assam")[0] == ((1971, 1981), "PRIMARY")
    assert s09.candidate_windows(1990, "Assam")[0] == ((1981, 1991), "PRIMARY")


def test_lineage_cycle_is_rejected():
    g = nx.DiGraph([("A", "B"), ("B", "C")])
    lineage_graph.assert_acyclic(g)
    g.add_edge("C", "A")
    with pytest.raises(AssertionError, match="cycle"):
        lineage_graph.assert_acyclic(g)


def test_ancestry_generations():
    rel = pd.DataFrame({"from_ck": ["A", "B"], "to_ck": ["B", "C"], "relationship_type": ["FORMED_FROM"] * 2,
                        "year_a": [1951, 1961], "year_b": [1961, 1971], "transfer_km2": [1.0, 1.0]})
    anc = lineage_graph.ancestry(lineage_graph.lineage_dag(rel))
    assert set(map(tuple, anc[anc.canonical_key == "C"][["ancestor_ck", "generations"]].values)) == {("B", 1), ("A", 2)}


def accounting_row(**kw):
    row = dict(event_id="a" * 32, predecessor_ck="IND-000001", pre_vintage=1991, post_vintage=2001,
               source_area_km2=100.0, declared_successor_km2=40.0, retained_km2=60.0,
               undeclared_neighbour_km2=0.0, displacement_km2=0.0, sliver_km2=0.0, unmapped_km2=0.0,
               closure_error_km2=0.0, closure_ok=True, n_events_same_window=1, measurement_status="MEASURED")
    row.update(kw)
    return pd.DataFrame([row])


def test_contract_rejects_measured_row_in_shared_window():
    schemas.validate("event_accounting", accounting_row())
    with pytest.raises(RuntimeError, match="V8"):
        schemas.validate("event_accounting", accounting_row(n_events_same_window=2))


def test_contract_rejects_bad_canonical_key():
    with pytest.raises(RuntimeError):
        schemas.validate("event_accounting", accounting_row(predecessor_ck="CK_1"))

"""Stage 08 — Probabilistic linkage of event names to district records (splink).

Replaces v2's exact (state, name) string lookup, hardcoded alias dictionary and
magic similarity thresholds with a Fellegi-Sunter model whose m/u parameters
are estimated from the data and written out for inspection.

  left   distinct (name, event_state) pairs from event participants
  right  one record per (canonical_key, vintage): the name and state mapped then

Comparisons
  name   exact / documentary alias (data/reference/name_aliases.csv) /
         Jaro-Winkler >= 0.95 / >= 0.88 / >= 0.80 / else
  state  exact / historically compatible (data/reference/state_lineage.csv) / else

The output lists every candidate record with its match probability. Choosing
among candidates is not done here: s09 restricts candidates to districts that
actually exchanged territory before accepting a name match.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import splink.comparison_level_library as cll
import splink.comparison_library as cl
from splink import DuckDBAPI, Linker, SettingsCreator, block_on

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

LK = lib.CFG["linkage"]


def with_keys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["alias_norm"] = df["name_norm"].map(lib.alias_key)
    df["state_compat"] = df["state_norm"].map(lambda s: sorted(lib.compatible_states(s)))
    return df


def build_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    pt = pd.read_parquet(lib.GOLD_EVENTS_DIR / "event_participant.parquet")
    left = (pt[["name_norm", "event_state_norm"]].drop_duplicates()
            .rename(columns={"event_state_norm": "state_norm"})
            .sort_values(["name_norm", "state_norm"]).reset_index(drop=True))
    left.insert(0, "uid", [f"P{i:05d}" for i in range(len(left))])

    obs = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_observation.parquet")
    right = pd.DataFrame({
        "canonical_key": obs.canonical_key, "year": obs.year,
        "name_norm": obs.district_name.map(lib.normalize_name),
        "state_norm": obs.state.map(lambda s: lib.normalize_name(lib.canonical_state(s))),
    }).sort_values(["canonical_key", "year"]).reset_index(drop=True)
    right.insert(0, "uid", [f"R{i:05d}" for i in range(len(right))])
    return with_keys(left), with_keys(right)


def settings() -> SettingsCreator:
    name = cl.CustomComparison(
        output_column_name="name",
        comparison_levels=[
            cll.NullLevel("name_norm"),
            cll.ExactMatchLevel("name_norm"),
            cll.ExactMatchLevel("alias_norm").configure(label_for_charts="documentary alias"),
            cll.JaroWinklerLevel("name_norm", 0.95),
            cll.JaroWinklerLevel("name_norm", 0.88),
            cll.JaroWinklerLevel("name_norm", 0.80),
            cll.ElseLevel(),
        ])
    state = cl.CustomComparison(
        output_column_name="state",
        comparison_levels=[
            cll.NullLevel("state_norm"),
            cll.ExactMatchLevel("state_norm"),
            cll.CustomLevel("list_contains(state_compat_l, state_norm_r) "
                            "OR list_contains(state_compat_r, state_norm_l)",
                            label_for_charts="compatible via state lineage"),
            # EM sees no true match with an incompatible state and estimates
            # m = 0, which would let a mis-filed state veto any name match.
            # A fixed floor keeps it strong-but-finite evidence against.
            cll.ElseLevel().configure(m_probability=LK["state_mismatch_m_floor"], fix_m_probability=True),
        ])
    return SettingsCreator(
        link_type="link_only",
        unique_id_column_name="uid",
        comparisons=[name, state],
        blocking_rules_to_generate_predictions=[
            block_on("name_norm"),
            block_on("alias_norm"),
            "substr(l.name_norm, 1, 3) = substr(r.name_norm, 1, 3)",
            "jaro_winkler_similarity(l.name_norm, r.name_norm) >= 0.80",
        ],
    )


def main() -> None:
    left, right = build_inputs()
    model_cols = ["uid", "name_norm", "alias_norm", "state_norm", "state_compat"]
    linker = Linker([left[model_cols], right[model_cols]], settings(), db_api=DuckDBAPI(),
                    input_table_aliases=["events", "districts"])
    linker.training.estimate_probability_two_random_records_match(
        [block_on("name_norm", "state_norm")], recall=0.7)
    linker.training.estimate_u_using_random_sampling(max_pairs=LK["u_sampling_max_pairs"], seed=LK["seed"])
    linker.training.estimate_parameters_using_expectation_maximisation(block_on("state_norm"))
    linker.training.estimate_parameters_using_expectation_maximisation(block_on("name_norm"))
    linker.misc.save_model_to_json(str(lib.EVENTS_OUTPUT_DIR / "s08_splink_model.json"), overwrite=True)

    pred = linker.inference.predict(threshold_match_probability=0.01).as_pandas_dataframe()
    ev = pred.uid_l.str.startswith("P")
    p = pd.DataFrame({
        "left_uid": pred.uid_l.where(ev, pred.uid_r),
        "right_uid": pred.uid_r.where(ev, pred.uid_l),
        "match_probability": pred.match_probability.round(10),
        "match_weight": pred.match_weight.round(8),
    })
    p = p.merge(left[["uid", "name_norm", "state_norm"]].rename(
        columns={"uid": "left_uid", "state_norm": "event_state_norm"}), on="left_uid")
    p = p.merge(right[["uid", "canonical_key", "year", "name_norm", "state_norm"]].rename(columns={
        "uid": "right_uid", "name_norm": "record_name_norm", "state_norm": "record_state_norm"}), on="right_uid")
    p = (p.drop(columns=["left_uid", "right_uid"]).astype({"year": int})
         .sort_values(["name_norm", "event_state_norm", "match_probability", "canonical_key", "year"],
                      ascending=[True, True, False, True, True]))
    lib.write_table(p, lib.GOLD_EVENTS_DIR / "participant_ck_candidate.parquet", "participant_ck_candidate")

    best = p.drop_duplicates(["name_norm", "event_state_norm"])
    print(f"event names: {len(left)}  district records: {len(right)}  candidate pairs: {len(p)}")
    print(f"names with a candidate >= {LK['min_match_probability']}: "
          f"{(best.match_probability >= LK['min_match_probability']).sum()} / {len(left)}")


if __name__ == "__main__":
    main()

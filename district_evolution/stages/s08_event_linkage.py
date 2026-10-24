"""Stage 08 — Probabilistic linkage of event names to district records (splink).

Replaces v2's exact (state, name) string lookup, hardcoded alias dictionary and
magic similarity thresholds with a Fellegi-Sunter model whose m/u parameters
are estimated from the data and written out for inspection.

  left   distinct (name, event_state) pairs from event participants
  right  one record per (canonical_key, vintage): the name and state mapped then

Comparisons
  name   exact / documentary alias (data/reference/name_aliases.csv) or same linkage key /
         stem Jaro-Winkler >= 0.95 / >= 0.88 / >= 0.80 (qualifiers equal) / else
  state  exact / the state holding the district's land today / lineal (the same land under a
         parent or child state: Uttarakhand <-> Uttar Pradesh, Chandigarh <-> Punjab) /
         sibling (shares a parent state: Kerala <-> Andhra Pradesh via Madras) / else

Linkage key (core.linkage_key): the alias-resolved name with number words as digits ("Twenty Four
Parganas" = "24 Parganas"), directional words in English ("Paschim Medinipur" = "Medinipur West")
and its qualifiers split off. Similarity is measured on the stem and the qualifiers must be equal:
on whole names a shared qualifier carried the score (Paschim Medinipur ~ Paschim Bardhaman) and
different ones barely lowered it (East Nimar ~ West Nimar, 0.87). An alias also resolves the
event side before a fuzzy comparison, so "Alleppey" (alias of Alappuzha) meets the map's
"Alapuzha" as a spelling variant; in 4.0.0 it met nothing.

Lineal and sibling states were one level in 4.0.0. Pooled, 7% of random pairs fell in it and EM
gave it a Bayes factor of 0.22, i.e. evidence AGAINST a match: an exact name filed under the
child state of a reorganisation (Saharanpur under Uttarakhand, Ambala under Chandigarh,
Trivandrum under Tamil Nadu) scored 0.14 and stayed unlinked. Lineal states share land; siblings
share only a parent, so they are separate levels and EM weighs each.

An event name written as alternatives ("Bhimnagar/Sambhal", s07) enters as one row per
alternative; s09 takes the best.

The events compilation files events under present-day states (a 1991 Dhanbad event is filed
under Jharkhand, created 2000; a 1957 Malabar event under Kerala), while each map record carries
the state printed on that map (Bihar, Madras). So each record is also compared through its
district's present-day state: the state of the reference-map district that holds most of the
land of the district's last observation (s03 REFERENCE overlay). Without this level, "exact name,
compatible state", the common case for every pre-reorganisation map, scored 0.506 against a 0.50
threshold and flipped with any change to the training data (4.0.0 audit).

The output lists every candidate record with its match probability. Choosing
among candidates is not done here: s09 restricts candidates to districts that
actually exchanged territory before accepting a name match.
"""

from __future__ import annotations

import json

import pandas as pd
import splink.comparison_level_library as cll
import splink.comparison_library as cl
from splink import DuckDBAPI, Linker, SettingsCreator, block_on

from district_evolution import core

LK = core.CFG["linkage"]


# gamma_name -> what the name comparison found (level order in settings(); -1 is the null level).
# s09 accepts a match outside any territorial footprint only on STRONG_NAME_EVIDENCE: the loosest
# spelling level (stem Jaro-Winkler 0.80-0.88: Akola ~ Kolaba, Bagalkot ~ Bangalore, Alappuzha ~
# Malappuram) is plausible only where the geometry has already narrowed the candidates.
NAME_EVIDENCE = {5: "EXACT", 4: "ALIAS_OR_KEY", 3: "SPELLING_0.95", 2: "SPELLING_0.88", 1: "SPELLING_0.80",
                 0: "NONE", -1: "NONE"}
STRONG_NAME_EVIDENCE = frozenset({"EXACT", "ALIAS_OR_KEY", "SPELLING_0.95", "SPELLING_0.88"})


def with_keys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["alias_norm"] = df["name_norm"].map(core.alias_key)
    keys = [core.linkage_key(n, s) for n, s in zip(df["name_norm"], df["state_norm"], strict=True)]
    df["stem"] = [k[0] for k in keys]
    df["quals"] = [k[1] for k in keys]
    df["stem_sorted"] = df["stem"].map(lambda x: " ".join(sorted(x.split())))
    df["state_lineal"] = df["state_norm"].map(lambda s: sorted(core.lineal_states(s)))
    df["state_compat"] = df["state_norm"].map(lambda s: sorted(core.compatible_states(s)))
    return df


def present_day_state(obs: pd.DataFrame) -> pd.Series:
    """canonical_key -> state of the reference-map district holding most of the land of its last
    observation (its own state if it is on the reference map)."""
    ref_year = core.REFERENCE_YEAR
    state_of = obs.set_index("geom_obs_id").state
    last = obs.sort_values(["canonical_key", "year"]).drop_duplicates("canonical_key", keep="last")
    flow = pd.read_parquet(core.GOLD_SPATIAL_DIR / "transition_flow.parquet",
                           columns=["kind", "year_b", "geom_obs_id_a", "geom_obs_id_b", "total_km2"])
    flow = flow[(flow.kind == "REFERENCE") & (flow.year_b == ref_year) & flow.geom_obs_id_a.isin(last.geom_obs_id)]
    main = (flow.sort_values(["geom_obs_id_a", "total_km2", "geom_obs_id_b"], ascending=[True, False, True])
            .drop_duplicates("geom_obs_id_a").set_index("geom_obs_id_a").geom_obs_id_b.map(state_of))
    today = last.set_index("canonical_key").geom_obs_id.map(main)
    own = last.set_index("canonical_key").state
    return today.where(today.notna(), own)


def build_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    pt = pd.read_parquet(core.GOLD_EVENTS_DIR / "event_participant.parquet")
    # one row per name a participant is written under ("Bhimnagar/Sambhal" -> both)
    pt = (pt.assign(name_norm=pt.name_alternatives_norm.str.split(";")).explode("name_norm"))
    pt = pt[pt.name_norm.str.len() > 0]
    left = (pt[["name_norm", "event_state_norm"]].drop_duplicates()
            .rename(columns={"event_state_norm": "state_norm"})
            .sort_values(["name_norm", "state_norm"]).reset_index(drop=True))
    left.insert(0, "uid", [f"P{i:05d}" for i in range(len(left))])

    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    state_key = lambda s: core.normalize_name(core.canonical_state(s))  # noqa: E731
    right = pd.DataFrame({
        "canonical_key": obs.canonical_key, "year": obs.year,
        "name_norm": obs.district_name.map(core.normalize_name),
        "state_norm": obs.state.map(state_key),
        "today_state_norm": obs.canonical_key.map(present_day_state(obs)).map(state_key),
    }).sort_values(["canonical_key", "year"]).reset_index(drop=True)
    # an event names one (present-day) state; compared with a record's own state and its district's state today
    left["today_state_norm"] = left["state_norm"]
    right.insert(0, "uid", [f"R{i:05d}" for i in range(len(right))])
    return with_keys(left), with_keys(right)


def settings() -> SettingsCreator:
    name = cl.CustomComparison(
        output_column_name="name",
        comparison_levels=[
            cll.NullLevel("name_norm"),
            cll.ExactMatchLevel("name_norm"),
            # two deterministic equivalences in one level, so EM estimates them together: a rare level of
            # its own got m ~ 0.001 and a Bayes factor of 32 (vs ~725 for an alias) from too few pairs
            cll.CustomLevel("alias_norm_l = alias_norm_r OR (stem_sorted_l = stem_sorted_r AND quals_l = quals_r)",
                            label_for_charts="documentary alias, or the same name up to qualifiers' language, "
                                             "numerals and word order"),
            *[cll.CustomLevel(f"jaro_winkler_similarity(stem_l, stem_r) >= {t} AND quals_l = quals_r",
                              label_for_charts=f"stem Jaro-Winkler >= {t}, qualifiers equal")
              for t in (0.95, 0.88, 0.80)],
            cll.ElseLevel(),
        ])
    state = cl.CustomComparison(
        output_column_name="state",
        comparison_levels=[
            cll.NullLevel("state_norm"),
            cll.ExactMatchLevel("state_norm"),
            cll.ExactMatchLevel("today_state_norm").configure(label_for_charts="district's state today"),
            cll.CustomLevel("list_contains(state_lineal_l, state_norm_r) "
                            "OR list_contains(state_lineal_r, state_norm_l)",
                            label_for_charts="lineal state (same land, parent or child state)"),
            cll.CustomLevel("list_contains(state_compat_l, state_norm_r) "
                            "OR list_contains(state_compat_r, state_norm_l)",
                            label_for_charts="sibling state (shares a parent state)"),
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
            block_on("stem"),
            "substr(l.name_norm, 1, 3) = substr(r.name_norm, 1, 3)",
            "jaro_winkler_similarity(l.name_norm, r.name_norm) >= 0.80",
            "jaro_winkler_similarity(l.stem, r.stem) >= 0.80",
        ],
    )


def stable_model(value):
    """splink stamps a random linker_uid and EM leaves ~1e-15 float noise; neither is model content."""
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, dict):
        return {k: stable_model(v) for k, v in value.items() if k != "linker_uid"}
    if isinstance(value, list):
        return [stable_model(v) for v in value]
    return value


def main() -> None:
    left, right = build_inputs()
    model_cols = ["uid", "name_norm", "alias_norm", "stem", "stem_sorted", "quals", "state_norm", "today_state_norm",
                  "state_lineal", "state_compat"]
    linker = Linker([left[model_cols], right[model_cols]], settings(), db_api=DuckDBAPI(),
                    input_table_aliases=["events", "districts"])
    linker.training.estimate_probability_two_random_records_match(
        [block_on("name_norm", "state_norm")], recall=0.7)
    linker.training.estimate_u_using_random_sampling(max_pairs=LK["u_sampling_max_pairs"], seed=LK["seed"])
    linker.training.estimate_parameters_using_expectation_maximisation(block_on("state_norm"))
    linker.training.estimate_parameters_using_expectation_maximisation(block_on("name_norm"))
    model = stable_model(linker.misc.save_model_to_json())
    (core.EVENTS_OUTPUT_DIR / "s08_splink_model.json").write_text(json.dumps(model, indent=4), encoding="utf-8")

    pred = linker.inference.predict(threshold_match_probability=0.01).as_pandas_dataframe()
    ev = pred.uid_l.str.startswith("P")
    if "gamma_name" not in pred:
        raise RuntimeError("splink predictions carry no gamma_name column; name_evidence cannot be recorded")
    p = pd.DataFrame({
        "left_uid": pred.uid_l.where(ev, pred.uid_r),
        "right_uid": pred.uid_r.where(ev, pred.uid_l),
        "match_probability": pred.match_probability.round(10),
        "match_weight": pred.match_weight.round(8),
        "name_evidence": pred.gamma_name.map(NAME_EVIDENCE),
    })
    p = p.merge(left[["uid", "name_norm", "state_norm"]].rename(
        columns={"uid": "left_uid", "state_norm": "event_state_norm"}), on="left_uid")
    p = p.merge(right[["uid", "canonical_key", "year", "name_norm", "state_norm"]].rename(columns={
        "uid": "right_uid", "name_norm": "record_name_norm", "state_norm": "record_state_norm"}), on="right_uid")
    p = (p.drop(columns=["left_uid", "right_uid"]).astype({"year": int})
         .sort_values(["name_norm", "event_state_norm", "match_probability", "canonical_key", "year"],
                      ascending=[True, True, False, True, True]))
    core.write_table(p, core.GOLD_EVENTS_DIR / "participant_ck_candidate.parquet", "participant_ck_candidate")

    best = p.drop_duplicates(["name_norm", "event_state_norm"])
    print(f"event names: {len(left)}  district records: {len(right)}  candidate pairs: {len(p)}")
    print(f"names with a candidate >= {LK['min_match_probability']}: "
          f"{(best.match_probability >= LK['min_match_probability']).sum()} / {len(left)}")


if __name__ == "__main__":
    main()

"""Restate a CSV of district statistics onto the 2025 districts, from the command line.

    python -m district_evolution.harmonize.cli rice.csv --out rice_2025.csv \\
        --name District --state State --year Year --value Production

Writes the result (one row per 2025 district and year) and, next to it, a matching report with
every input row, how it was matched and, for rows that were not, candidate identities. Reads the
release (data/release/tables; --tables to use another). A rate (yield) is refused: harmonize its
numerator and denominator, then divide.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from district_evolution import core
from district_evolution.harmonize import restate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("csv", type=Path)
    p.add_argument("--out", type=Path, required=True, help="result CSV; the matching report is written beside it")
    p.add_argument("--name", default="district", help="column with the district name (default: district)")
    p.add_argument("--state", default="state", help="column with the state; '' if there is none")
    p.add_argument("--year", default="year", help="column with the year the value is for")
    p.add_argument("--value", default="value", help="column with the value")
    p.add_argument("--indicator", default=None, help="name for the indicator in the output (default: the value column)")
    p.add_argument("--kind", choices=["extensive", "ratio"], default="extensive")
    p.add_argument("--map-year", type=int, default=None, help="the map the figures report on, if the source says so")
    p.add_argument("--tables", type=Path, default=core.RELEASE_DIR / "tables")
    a = p.parse_args(argv)

    raw = pd.read_csv(a.csv, dtype=str)
    missing = [c for c in (a.name, a.year, a.value) + ((a.state,) if a.state else ()) if c not in raw.columns]
    if missing:
        p.error(f"{a.csv} has no column {', '.join(missing)}; columns are {', '.join(raw.columns)}")
    df = pd.DataFrame({"name": raw[a.name], "state": raw[a.state] if a.state else "", "year": raw[a.year], "value": raw[a.value]})
    try:
        links, harmonized = restate.restate(df, a.kind, a.indicator or a.value, a.map_year, a.tables)
    except (ValueError, restate.engine.RatioAllocationError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    harmonized.to_csv(a.out, index=False)
    report = a.out.with_name(a.out.stem + "_matching_report.csv")
    links.assign(candidates=links.candidates.map(lambda cs: " ".join(c["canonical_key"] for c in cs))).to_csv(report, index=False)
    counts = links.link_status.value_counts().to_dict()
    print(f"{len(links)} rows: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"wrote {a.out} ({len(harmonized)} rows) and {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

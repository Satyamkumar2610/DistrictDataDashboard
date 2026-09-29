"""Stage e01 — Evidence claims.

Every registered evidence source (district_evolution/evidence, EVIDENCE_SOURCES) turns its
statements into cited claims: NAME, AREA, INCEPTION, PARENT. A claim is what a source says,
nothing more; e02 locates its subject and e03 compares it with the maps.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core
from district_evolution.evidence import EVIDENCE_SOURCES


def main() -> None:
    claims = pd.concat([s.claims() for s in EVIDENCE_SOURCES], ignore_index=True).sort_values("claim_id")
    core.write_table(claims, core.GOLD_EVIDENCE_DIR / "evidence_claim.parquet", "evidence_claim",
                     csv_copy=core.EVIDENCE_OUTPUT_DIR / "e01_evidence_claim.csv")
    print(claims.groupby(["source_id", "claim_type"]).size().to_string())


if __name__ == "__main__":
    main()

"""Freeze an external reference snapshot of Indian districts from Wikidata.

Wikidata is independent of both the Stanford/SOI geometry and the events CSV,
so it can audit v3 outputs. It is crowd-maintained, so it is a corroboration
source, not ground truth: every area claim is kept with its own reference
("stated in") and point-in-time qualifier where Wikidata records one.

The live query result is written once to a dated JSON file; the audit reads
the snapshot, so the audit is reproducible even as Wikidata changes.

Usage: python -m district_evolution.evidence.wikidata_snapshot
Writes data/reference/external/wikidata_districts_<YYYY-MM-DD>.json
"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import certifi

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "reference" / "external"
ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "DistrictEvolution-audit/3.0 (research; github.com/Satyamkumar2610/architecture)"

# Q1149652 = district of India. Former districts keep P31 and carry P576 (dissolved).
QUERIES = {
    "items": """
SELECT ?d ?label ?coord ?inception ?dissolved ?state ?stateLabel WHERE {
  ?d wdt:P31 wd:Q1149652 .
  OPTIONAL { ?d rdfs:label ?label FILTER(LANG(?label) = "en") }
  OPTIONAL { ?d wdt:P625 ?coord }
  OPTIONAL { ?d wdt:P571 ?inception }
  OPTIONAL { ?d wdt:P576 ?dissolved }
  OPTIONAL { ?d wdt:P131 ?state . ?state rdfs:label ?stateLabel FILTER(LANG(?stateLabel) = "en") }
}""",
    "areas": """
SELECT ?d ?amount ?unit ?pointInTime ?statedInLabel WHERE {
  ?d wdt:P31 wd:Q1149652 ; p:P2046 ?st .
  ?st psv:P2046 [ wikibase:quantityAmount ?amount ; wikibase:quantityUnit ?unit ] .
  OPTIONAL { ?st pq:P585 ?pointInTime }
  OPTIONAL { ?st prov:wasDerivedFrom/pr:P248 ?statedIn .
             ?statedIn rdfs:label ?statedInLabel FILTER(LANG(?statedInLabel) = "en") }
}""",
    "lineage": """
SELECT ?d ?prop ?target ?targetLabel WHERE {
  VALUES ?prop { wdt:P807 wdt:P1365 wdt:P1366 }
  ?d wdt:P31 wd:Q1149652 ; ?prop ?target .
  OPTIONAL { ?target rdfs:label ?targetLabel FILTER(LANG(?targetLabel) = "en") }
}""",
}


def run(query: str) -> list[dict]:
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
        rows = json.load(resp)["results"]["bindings"]
    return [{k: v["value"] for k, v in r.items()} for r in rows]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot: dict[str, Any] = {"source": "Wikidata SPARQL endpoint", "endpoint": ENDPOINT,
                "retrieved": date.today().isoformat(), "queries": QUERIES,
                "results": {name: run(q) for name, q in QUERIES.items()}}
    out = OUT_DIR / f"wikidata_districts_{snapshot['retrieved']}.json"
    out.write_text(json.dumps(snapshot, indent=1, sort_keys=True), encoding="utf-8")
    for name, rows in snapshot["results"].items():
        print(f"{name}: {len(rows)} rows")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

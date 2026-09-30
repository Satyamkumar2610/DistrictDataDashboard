# Contributing

This pipeline answers four questions about every Indian district since 1951 (identity, origin,
fate, quantity) and restates district statistics on the 2025 districts. Contributions must keep
those answers traceable: every number comes from a table row, every threshold from
`config/pipeline.yaml` with a measured rationale, every table through a contract.

Read `docs/architecture/REVAMP_PLAN_V3.md` before changing identity, lineage or product meaning.

## Set up and check your change

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pip install -e . --no-deps && .venv/bin/pre-commit install
source .venv/bin/activate
python -m district_evolution build            # every stage in dependency order (or: dvc repro, with caching)
python -m district_evolution validate         # the gate; exits 1 on any ERROR check
pytest -q tests                               # unit tests, golden histories, baselines
ruff check district_evolution tests scripts examples && mypy
```

CI runs lint and type checks, builds twice, and fails on any byte difference between the builds
(except the outputs listed in `config/pipeline.yaml` under `determinism`), on any ERROR check, and on
any failing test.

Code rules, enforced by ruff and mypy (`pyproject.toml`): `zip()` is always `strict=True` unless unequal
lengths are the point (then `strict=False` with a comment); stage code is checked for attribute and
return errors, the library layer (`core`, `contracts`, `harmonize`, `release`, `sources`) for everything.

Curated reference files (`data/reference/`) are source: add rows only with the evidence the file's
column asks for, and `tests/test_reference_data.py` must pass. Proposed rows from rules
(`scripts/curation/`) are reviewed before they are written.

## Adding things without touching the core

Each kind of input has one interface (`district_evolution/core/interfaces.py`). A contribution of
this kind should not need changes under `district_evolution/stages/` or `district_evolution/core/`.

| You are adding | Write | Register | Contract |
|---|---|---|---|
| A boundary map series | a `BoundarySource` in `district_evolution/sources/` | `sources.SOURCES` | `boundary_layer` (checked on load) |
| Corroborating evidence | an `EvidenceSource` in `district_evolution/evidence/` | `evidence.EVIDENCE_SOURCES` | `evidence_claim` |
| A district statistic from a file | nothing: a config entry | `config/indicators.yaml` | `stat_observation` |
| A weight method (e.g. cropland) | a `WeightMethod` in `district_evolution/harmonize/weights.py` | `WEIGHT_METHODS` | `statistical_crosswalk` |

Every outside source also gets an evaluation page, `docs/sources/<source>.md` (template in
`docs/sources/README.md`): licence, coverage, and which boundaries it reports on. Check the licence
first; see `docs/decisions/licensing.md` for why.

## Rules the review will check

- **Geometry decides identity and area.** Names and outside evidence only corroborate or break ties
  among spatially valid candidates. Never resolve an identity from a name alone.
- **One class per km².** Never normalise weights to 1, redistribute a residual or force it to zero.
- **One meaning per column and product.** Every released column has a meaning in
  `district_evolution/contracts/descriptions.py`; the data dictionary is generated from it.
- **Disagreements are findings.** They go to the research queue (e04); nothing is auto-corrected.
- **Curated reference rows** (`data/reference/*.csv`) need evidence and a citation; rules that
  change the build read only rows marked CONFIRMED. A research question closes only through a row
  in `data/reference/research_findings.csv`.
- **Determinism.** IDs from `core.stable_id`, explicit sorts before any tie-break, seeded models.
- **Versions.** A change that renumbers canonical keys or changes a product's meaning is MAJOR:
  bump `pipeline_version` (and `pyproject.toml`, `CITATION.cff`), add to `CHANGELOG.md`, extend the
  key migration map. Any change to a regression count adds `tests/baselines/v<version>.yaml` with
  the delta explained.

## Pull requests

One work item per pull request. The description lists what changed, the baseline table (or "no
change"), the gate result from `outputs/pipeline/s12_validation_report.md`, and any threshold added
or changed with its rationale.

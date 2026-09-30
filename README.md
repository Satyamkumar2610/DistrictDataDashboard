# District Evolution

India had 316 districts on the 1951 map and 742 on the 2025 map. For every district on every one of
nine boundary maps (1951–2021 census-era maps, Survey of India 2025), this pipeline answers:

- **Identity**: is it the same administrative entity as an earlier one?
- **Origin**: which earlier districts did its land come from?
- **Fate**: where did its land go?
- **Quantity**: how many km² moved, and between which maps?

and restates statistics reported on any of those maps onto the 2025 districts (harmonization).

Geometry decides; names, an events compilation and Wikidata only corroborate. Every table passes a
data contract, every threshold is configured with a measured rationale, and two builds from the
same inputs are byte-identical.

> **Data licensing is unresolved.** The 1951–2021 maps are licensed to Stanford University
> affiliates by their publisher, and the terms forbid reproduction without permission. Read
> `docs/decisions/licensing.md` before using or redistributing anything under `data/`.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e . --no-deps
source .venv/bin/activate && dvc repro                  # ~4 min: build, evidence, harmonization, release, gate
pytest -q tests
(cd web && npm ci && npm run build)                       # the web platform (Node 22+)
uvicorn district_evolution.release.api:app              # platform at http://127.0.0.1:8000, API reference at /docs
```

To restate your own district statistics on the 2025 districts: the Harmonize page, or
`python -m district_evolution.harmonize.cli your.csv --out result.csv` (see
`docs/operations/harmonize_your_data.md`).

For development, run the API with uvicorn and `npm run dev` in `web/` (Vite proxies `/api`).
Browser tests: `npm run test:e2e` in `web/` (uses the installed Chrome; `PW_CHANNEL=chromium` for Playwright's own).

The gate report is `outputs/pipeline/s12_validation_report.md`; the data dictionary is
`docs/data_dictionary.md`; the release (tables, simplified geometry, DuckDB `load.sql`) is
`data/release/`.

## Layout

| Path | What |
|---|---|
| `district_evolution/stages/` | s01–s12 core pipeline, e01–e04 evidence, h01–h05 harmonization, r01–r02 release |
| `district_evolution/core/` | config, the one area method, IDs, names, reference tables, table writer, interfaces |
| `district_evolution/contracts/` | pandera contracts and the meaning of every column |
| `district_evolution/sources/`, `evidence/`, `harmonize/` | plug-in points for maps, evidence and statistics |
| `district_evolution/release/` | release definition and the read-only API (JSON, vector tiles) |
| `web/` | the web platform (atlas with side-by-side compare, states, harmonize your data, evidence, district histories and family trees, crosswalk, research queue, downloads): React, TypeScript, MapLibre GL, Apache ECharts, Playwright tests |
| `config/` | `pipeline.yaml` (every threshold), `sources.yaml`, `indicators.yaml` |
| `data/reference/` | curated reference tables (confirmed rows only) and research findings |
| `docs/` | design (`architecture/`), decisions, operations runbooks, data dictionary |

## Contributing and citing

See `CONTRIBUTING.md`. Cite with `CITATION.cff`; versions and their changes are in `CHANGELOG.md`.

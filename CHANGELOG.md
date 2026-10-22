# Changelog

Versions follow semantic versioning of `pipeline_version` (config/pipeline.yaml).
A MAJOR change can renumber canonical keys or change the meaning of a product.

## 4.1.0 (unreleased)

MINOR: no canonical key changes (`ck_registry`, `ck_observation` and `district_relationship` are identical
to 4.0.0). Deltas for every regression count are explained in `tests/baselines/v4.1.0.yaml`.

### Event linkage (s07-s09)
- **Compound names are parsed, not guessed.** "Parts of X", "A and B", "A/B" and comma lists are split by
  `core.parse_participants` only when every piece is a district name the maps or aliases know, so a
  district called "Daman and Diu" stays whole. "Parts of" marks the participant `partial`. Alternative
  spellings ("A/B") are each compared and the best kept.
- **A linkage key for names.** `core.linkage_key` resolves aliases, turns number words into numerals and
  translates directional qualifiers (Paschim -> West, Purba -> East, Uttar -> North, Dakshin -> South,
  Madhya -> Central) and separates them from the stem. Spelling similarity never links two names whose
  qualifiers differ (East Jaintia Hills is no longer a spelling of West Jaintia Hills).
- **Priors that match the search.** The splink probability uses a map-wide prior (about 1 in 900). s09
  searches a much smaller set: the predecessor's footprint, or the districts of one state. It now re-bases
  the Bayes factor on that set's prior (`linkage.footprint_prior` 0.9, measured 0.965;
  `linkage.state_scope_prior` 0.9, measured 0.994) instead of reusing the map-wide posterior. A map-wide
  link without footprint or state evidence now needs strong name evidence (exact, alias/key or Jaro-Winkler
  >= 0.88 on the stem); weak spelling matches such as Akola ~ Kolaba are refused.
- The state comparison distinguishes lineal states (a state and its successors or predecessors) from
  sibling states. The pooled level had a Bayes factor of 0.22, so correct historical states counted against
  a link.
- `participant_ck_candidate` records the name evidence of every candidate; V27 checks only strong-name classes.
- Result: 1,136 links (was 1,103), 93 unresolved names (was 124), 27 outside the footprint (was 35); 457 lineage edges corroborated by an event (was 436);
  402 events measured exactly (was 399). Corrections include Delhi North/North East/North West, Imphal
  East/West, East Jaintia Hills and West Jaintia Hills (was West Khasi Hills) and East Siang (was West Siang).
- Seven aliases: Khargone -> West Nimar and Khandwa -> East Nimar (renames recorded in the events
  compilation), and five spellings (Punch, Sahranpur, Pasumpon Thevar Thir, Midnapur, Cudappah).

### Lineage and overlay
- **Reversals.** `measured_area_transfer` gains `reversal_km2` and `is_reversed`: land that moves from A to
  B and at least 80% of it returns from B to A within two windows (`lineage.reversal_share`,
  `reversal_windows`). 572 of 1,371 transfers (37,388 km²) are flagged; they are more likely differences
  between map editions than administrative transfers. Nothing is removed or netted.
- **Numerical noise floor.** Overlay parts under 1e-6 km² (`overlay.numerical_noise_km2`) are GEOS
  round-off, not territory. They made `transition_flow` differ between Linux and macOS (51,765 vs 51,767); it now has 48,578 rows.

### Validation
- V17 can be exempted by a reviewed row in `data/reference/reviewed_exceptions.csv`, only while the
  measured value stays at or below the reviewed maximum. One row: the 0.074 km² New Delhi / Central overlap
  on the Stanford 2001 map, accepted by the owner. Gate: PASS with no warnings.

### Harmonization
- Two statistics that link to the same identity in the same year are `DUPLICATE_IDENTITY` and are not
  allocated (they were allocated twice). The API summary reports the count.

### Platform
- Error handling: API errors are typed; only network and server errors are retried. A page that fails shows
  an error with a retry, not a blank screen; a stale bundle after a deploy offers a reload; an outage shows a
  banner that recovers when the API returns.
- Icon buttons meet the 44 px touch target on touch screens; hover styles do not stick on touch.
- The district page shows which transfers come back later.

## 4.0.0 (unreleased)

MAJOR: canonical keys change. Every 3.x key resolves through `data/reference/ck_migration_v3_to_v4.csv`
(461 identical, 314 renumbered, 20 merged in 10 pairs, 9 retired). Deltas for every regression count are
explained in `tests/baselines/v4.0.0.yaml`.

### Identity
- **Placeholders.** The nine "Disputed (...)" strips on the SOI 2025 map (0.7-14.5 km², 50.3 km²) are
  excluded in s01 like the unnamed J&K polygons (config `placeholders`; logged with reason
  `DISPUTED_BOUNDARY_STRIP`). They had keys and counted as active districts: 733 active on the 2025
  map, not 742. Invariant V25 (ERROR): no placeholder holds an identity.
- **Growth continuation (OD-02).** A district that stays whole (r ≥ 0.90), keeps its name and grows keeps
  its identity when no other district continues into its successor (`GROWTH_NAME_RETAINED`; config
  `identity.growth_continues`, `growth_min_h`). Ten cases: Una 1991, Gandhinagar, Hyderabad and Kanpur
  Nagar 2001, Chennai, Mumbai, Punch and New Delhi 2021, Champhai and Kolkata 2025. 785 identities (was
  804), 52 closed (was 62). The three MERGED_INTO edges into Champhai are gone: Champhai continues, and
  Khawzawl's and Saitual's land reaches it as measured transfers. `docs/decisions/OD-02_growth_continuation.md`.

### Event linkage
- **The linkage decision sat on a knife-edge.** "Exact name, historically compatible state", the usual
  case for any map before a state reorganisation, scored 0.506 against a 0.50 threshold. A 0.05 change in
  one learned weight (from adding correct aliases) flipped 356 candidate pairs and 99 links, including
  names unrelated to the change. s08 now also compares an event's state with the state holding the
  district's land today (the events compilation files events under present-day states: a 1991 Dhanbad
  event under Jharkhand), and the threshold sits in the gap between classes (0.52; no current decision
  changes). Check V27 (WARNING) flags any probability class that drifts within 0.015 of the threshold.
- Result: 1,103 links (was 1,094), 124 unresolved names (was 132), 35 outside the footprint (was 42),
  436 lineage edges corroborated by an event (was 431). Corrections include Raigarh 1998 (was linked to
  Raygad, Maharashtra) and Manipur East/West (were swapped). Results now move by < 0.5% when the alias
  list changes (they moved by 9% before).
- **55 aliases** added by a stated rule with two kinds of evidence each (`scripts/curation/propose_aliases.py`):
  39 renames the events compilation records between two names one identity carries on consecutive maps,
  16 spellings with the same consonant skeleton. Pairs whose names belong to another identity anywhere are
  refused (Kolaba -> Raigarh would have captured Raigarh, Chhattisgarh).

### Products and checks
- `crosswalk_coverage` (released): for each district on each earlier map, how much of it the 2025
  districts cover and how much they do not. Invariant V26 (ERROR): it adds up exactly.
- `products.min_source_share` and `products.arithmetic_tol_km2` moved into config (were hard-coded).
- `known_geometry_gaps.csv` records Andhra Pradesh (2022) and Rajasthan (2023) as `EVENTS_ONLY`: the
  events compilation dates their new districts, the SOI 2025 map does not show them.
- Wikidata (e01-e03) is an internal gate check: not released, served or shown; the released research
  queue omits its topic. `/api/evidence/*` and the Evidence page removed; `/api/districts/{ck}/research`
  replaces `/api/districts/{ck}/evidence`.
- Stage a02 credibility audit (`outputs/audit/CREDIBILITY_AUDIT.md` + CSVs) and a fixed expert-review
  sample (`review_sample.csv`, verdicts in `data/reference/review_outcomes.csv`, error rate with a 95%
  interval). `docs/audit/credibility_report.md`.

### Engineering
- `python -m district_evolution` CLI: `build` (stage order derived from dvc.yaml, per-stage timings in
  `logs/`), `stages`, `validate` (exit 1 on an ERROR check), `info`, `harmonize`, `serve`.
  `scripts/run_all.sh` ran 12 of 25 stages and would have failed at s11 on a clean checkout; it now calls
  the CLI.
- The release records its provenance: pipeline version, config hash, a sha256 of the package's code, Python
  and package versions. Content-addressed rather than a git commit, so a release's hash in dvc.lock stays
  valid across commits that do not change it; `info` also prints the commit.
- ruff and mypy configured and clean; every `zip()` is `strict=True` unless unequal lengths are intended.
  CI runs them; `requirements-dev.txt`, `.pre-commit-config.yaml`; tests for the CLI, the curated
  reference files and the identity rules.

### Harmonization: cropland weights (WP4 completed)
- `CROPLAND` weight method (`harmonize/cropland.py`): a cropland raster declared under `weights.cropland`
  in `config/indicators.yaml` is summed over each map overlaid on the 2025 map; weight = cropland in
  source ∩ target / cropland in source. Each cell belongs to the districts its centre lies in, so
  cropland is partitioned like land; cropland outside the crosswalk stays in the denominator (weights sum
  to at most 1, never normalised). Lon/lat cells take their area from `core.geodesic_area_km2`. The raster
  is read in row blocks (bounded memory). Impossible values (fraction > 1, more cropland than the cell,
  negative) and rotated or CRS-less rasters are refused. `rasterio` added (pipeline only, not the platform).
- No raster is declared yet (the owner supplies it), so every output value is unchanged: AREA remains the
  only method and the new tables are empty. `docs/operations/cropland_weights.md`.
- New tables, contracts and gate checks: `cropland_coverage` (per source district: cropland, how much
  the weights carry, nodata area) and `harmonization_method_sensitivity` (each 2025 district's value
  under CROPLAND against AREA, flagged beyond `harmonize.sensitivity_flag_rel`, a provisional 0.25 to be
  measured on the first raster). Both released; `/api/districts/{ck}/harmonized` returns the sensitivity
  rows and the District page shows them. h05 checks conservation per method and reports the comparison.
- An indicator can limit its methods (`methods:`); the mapped-area self-check is AREA only.
- `config/indicators.yaml` entries are checked on load (all four columns mapped, unique codes, kind).
- Tests on synthetic rasters (exact zonal sums, blocking, units, refusal, projected grids) and the WP4
  case: with cropland everywhere but Lahaul & Spiti, AREA sends 46% of a 1951 Kangra total there and
  CROPLAND none.

### Platform hardening
- `GET /api/health`: liveness and readiness (the container HEALTHCHECK and CI use it).
- Responses over 1 KB are gzip-compressed; every response carries `X-Content-Type-Options`,
  `X-Frame-Options` and `Referrer-Policy`.
- Request bodies over `harmonize.max_request_bytes` (16 MB) are refused with 413 before parsing, by
  declared length or by counting a streamed body.
- A test checks that the API imports no library outside `requirements-platform.txt` (the container
  installs only that); it caught the harmonize package importing geopandas through `core.interfaces`.
- Measured over HTTP on a laptop (13 endpoints, 30 requests each, while a build ran): p50 2.7 ms,
  p95 8.0 ms (target 200 ms).

### Web platform: audit and overhaul
- An audit of every route at desktop and phone width (screenshots, axe-core, text and target sizes, timings),
  with the plan and the measured results in `docs/design/ui_overhaul.md`.
- Stylesheet rebuilt on a type scale (15 px body, nothing under 12 px), the spacing scale, three surface levels
  and 36 px controls (44 px on touch). Colour tokens unchanged; charts now colour by meaning.
- Navigation grouped into Explore, Use the data and About; a phone menu with every section and a search.
- District page: a sticky section bar; row hashes moved out of visible text into the source line's tooltip.
- State page: the map fits the state (`/api/states/{state}` returns `bbox`).
- Phone Atlas: colour controls fold away so the map keeps the screen.
- Harmonize: a drop zone for the CSV. Loading: skeletons instead of "Loading…".
- Accessibility: axe reports no serious or critical violation on any route (was 4 routes); every scroll region
  is keyboard-reachable; text on the selection tint is contrast-tested.

### Web platform: 3D map and depth
- The home page opens on a 3D map of India drawn from the release's own district polygons (three.js, bundled; no
  external service). It plays through the nine maps; the districts that first appear on each map rise and are
  coloured `--new`. Hover names a district and its area; a click opens its page. Counts in the caption and on the
  map equal `/api/overview` for every map (`web/e2e/map3d.spec.ts`). Reduced motion: no autoplay, no camera drift.
  Without WebGL the panel points to the Atlas.
- `GET /api/shapes/{year}`: every district on a map as light GeoJSON (simplified 0.04°, 0.001° precision) for
  drawing, never for measurement; 55 KB (1951) to 95 KB (2025) gzipped; cached.
- Glass panels where controls sit over the map.
- Motion that answers an action (`web/src/motion.ts`): page changes and filters as View Transitions (the app now uses a
  data router so links can run them), a circular theme reveal from the toggle, a year highlight that glides, menus,
  suggestions and definitions that grow in, sections that expand to height, a sliding Atlas selection panel. The
  earlier slide-in on every section and lift on every card are removed. Reduced motion turns all of it off.

### Hosting
- `DISTRICT_AUTH_PASSWORD` puts HTTP Basic in front of the whole app — the web pages, the vector
  tiles, every JSON endpoint and `/api/download/*.parquet` — as the outermost middleware, so nothing
  is served and no request body is read before the password is checked. Only `/api/health` stays
  open, for a platform health check that holds no credentials. Unset, the app runs open and says so
  at startup: right for localhost, wrong for an address.
- `fly.toml` and `docs/operations/hosting.md`: a private instance on Fly (or Render, Railway, a VPS),
  with the release on a mounted volume and never in the image, because the image can be pushed to a
  registry and the 1951-2021 maps cannot (`docs/decisions/licensing.md`).
- Six tests cover the lock: refused without the password, served with it, refused on a wrong user or
  password, malformed credentials rejected without crashing, and the health path still open.

### Web platform colours
- Four light-theme tokens failed WCAG against the grounds the UI renders text on (`--bg`, `--surface`).
  Hue and saturation held, lightness lowered: `warn` `#b97c00` -> `#986600` (3.53:1 -> 4.96:1 on
  surface; chips and captions set *text* in it at 11-13px, not only borders), `good` `#0c8a0c` ->
  `#0b820b` (4.12:1 -> 4.55:1 on bg), `muted` `#6d7a74` -> `#66726d` (4.09:1 -> 4.57:1 on bg), and
  `in` `#1baf7a` -> `#1aa875` (2.82:1 -> 3.04:1, the 3:1 bar for a legend swatch and map fill).
- `tests/test_theme_contrast.py` (49 checks) parses `web/src/theme.css` directly and holds two bars,
  because the tokens do two jobs: 4.5:1 for anything the UI sets text in, 3:1 for a fill or swatch
  that carries meaning. Two exemptions, each with its reason in the test: `neutral` is the absence of
  a classification and is meant to recede; `gain`/`loss` sit at near-equal lightness **on purpose** --
  a diverging scale, hue carrying direction and lightness magnitude. Simulated under deuteranopia,
  protanopia and tritanopia (Vienot matrices) they stay 113-162 of 255 apart per channel, so the test
  checks that separation instead of a lightness difference that would break the scale.
- The design system (tokens, per-token usage, the measured ratios) is published from this same file,
  so the two cannot drift: `docs/operations/design_system.md`.

### Fixed
- h01 did not depend on the supplied statistics files: replacing a file under `data/bronze/agri/` would
  not rerun harmonization under `dvc repro`. h01 now depends on `data/bronze/agri/` and h02 on
  `data/bronze/cropland/`; `.gitignore` no longer hides supplied statistics CSVs; a test checks that every
  declared input lives under a dependency.
- V19 crashed when there was nothing to report (an empty list used as a row mask selects columns).
- The harmonization engine crashed on a state with no districts on the map (same cause); now UNLINKED.
- The audit counted one returning flow twice when two earlier flows preceded it.
- An unknown `/api/...` path returned the web app with status 200; now a JSON 404.

## 3.9.0

Evidence insights, a container for the platform, and runnable examples. No key, lineage, area,
product, evidence or harmonization changes.

### Added
- Evidence page: verdicts by kind of claim and conflicts by state (both filter the claim list),
  our area against Wikidata's on log axes (click a point to open the district), every reason code
  with its meaning, and a claim list linked to the district, the Wikidata item and its open
  research question. API: `/api/evidence/summary`, `/api/evidence/claims`.
- The research queue keeps its topic and filter in the URL, so other pages link to a question.
- Container: `Dockerfile`, `compose.yaml`, `requirements-platform.txt`,
  `docs/operations/deploy.md`. The release is mounted read-only at run time and never copied into
  the image (licensing). Runs as an unprivileged user on a read-only file system. CI builds it and
  runs the browser tests against it (`PW_BASE_URL` in `web/playwright.config.ts`).
- `examples/`: five questions in plain DuckDB SQL over the release, restating statistics from an
  old map, and a district's family tree with networkx. `tests/test_examples.py` runs them.

## 3.8.0

Harmonize your own data. No key, lineage, area, product, evidence or harmonization-output changes.

### Added
- `harmonize/restate.py`: restate a user's district statistics onto the 2025 districts without a
  rebuild, from a release's tables, with the same `link` and `allocate` as h01-h03. Every row comes
  back with a status (LINKED, AMBIGUOUS, UNLINKED, BEFORE_FIRST_MAP, NO_VALUE) and, when not linked,
  candidate identities with a similar name on that map (`harmonize.suggest`); nothing is guessed.
- `python -m district_evolution.harmonize.cli`: the same from the command line (result CSV and a
  matching report).
- `POST /api/harmonize` (processed in memory, not stored; `harmonize.max_request_rows`) and the
  Harmonize page: upload a CSV, map its columns, see matches, a map and table of the result, and
  download both. A rate is refused with the reason.
- `docs/operations/harmonize_your_data.md`; 5 Python and 3 browser tests. Restating the 1991 map's
  own areas from the release reproduces h03's mapped-area result for 1991.

### Changed
- `engine.link`, `engine.allocate` and `AreaWeight.weights` take an optional `tables` directory
  (default: the pipeline's outputs, as before). `link` matches a row with no state against the
  whole map.

## 3.7.0

Platform insights. No key, lineage, area, product, evidence or harmonization changes.

### Added
- Atlas compare mode: two maps side by side, moving together (`/atlas?compare=1&year=1981&year2=1971`).
- States pages: each state's districts on every map, and every lineage edge into its districts,
  window by window, with its `district_relationship` row. A district identity belongs to the state
  that holds most of its land on the 2025 map (`crosswalk_to_reference`), so early districts count
  under their present state.
- District family tree: every ancestor and descendant placed at the map on which it first appears,
  coloured by relationship, line width by km² moved.
- Downloads of every release table as CSV or Parquet from the Data page.
- API: `/api/states`, `/api/states/{state}`, `/api/districts/{ck}/genealogy`,
  `/api/download/{table}.{csv|parquet}`; 4 Python tests and 4 browser tests.

## 3.6.0

The web platform. No key, lineage, area, product, evidence or harmonization changes.

### Added
- `web/`: React + TypeScript (Vite), MapLibre GL and Apache ECharts, all open source; fonts
  self-hosted; no third-party basemap (works offline, no tile licence). Pages: Overview (release
  figures), Atlas (every district on any of the 9 maps; colour by new identity or area change),
  District (one identity through every map, with the land it gave or received in each window drawn
  and its km² from the measured tables, lineage Sankey, events, Wikidata verdicts, open questions,
  harmonized values), Crosswalk (area weights to 2025, CSV download), Research queue, Data and
  quality (gate, release, data dictionary). Every caption names its source table and row.
- API under `/api`: vector tiles per map built by DuckDB (`ST_AsMVT`, no tile server), change
  parcels, overview, validation, dictionary. The event-level measurement status follows s09's rule
  (401 / 186 / 22). The release carries its validation checks and the dictionary.
- Playwright browser tests (6) and CI steps that build the app and run them against the release.

### Removed
- `release/explorer.html` (replaced by the platform).

### Added (Phase 5 groundwork, open data lab)
- `README.md`, `CONTRIBUTING.md` (adding a map source, evidence source, indicator or weight method
  without touching `stages/` or `core/`; review rules), `tests/test_extensibility.py` (an indicator
  added by config alone is linked and harmonized).
- `docs/decisions/licensing.md`: the 1951–2021 maps are licensed to Stanford affiliates only and
  may not be reproduced without permission; the public repository contains them. The owner must
  decide before any data release; LICENSE files wait for that decision.

## 3.5.0

Phase 4: the harmonization engine. No key, lineage, area, product or evidence changes.

### Added
- Stages h01–h05 and `config/indicators.yaml`. h01 links each reported value to the identity that
  carried its name in the same (or a historically compatible) state on the map it reports on:
  the latest map depicting no later than its year, or the map the source declares. h02 builds
  weights (AREA from `crosswalk_to_reference`, each row with a stated assumption). h03 allocates
  extensive totals; allocating a ratio raises. h04 recomputes ratios such as yield from harmonized
  numerator and denominator. h05 checks conservation and a self-check: harmonizing every district's
  own mapped area reproduces `district_reference_context.mapped_km2` for all 6,678 district-years
  (max difference 7e-12 km²; 4,614 of 4,614 values linked to the correct identity).
- A value whose district changed between its map and its year is flagged `boundary_uncertain`;
  districts that did not report lower `coverage_score`; nothing is imputed.
- Check V24 (ERROR): harmonized totals not conserved. Harmonized tables in the warehouse, the
  release, the dictionary and the API (`/districts/{ck}/harmonized`).
- `docs/sources/README.md`: the evaluation every outside source needs before ingestion.

### Waiting for data (by decision)
- Crop statistics and a cropland raster: the owner will supply them. The engine, contracts and
  checks are in place; a `CROPLAND` weight method and the method-sensitivity report (area vs
  cropland, Kangra 1951 as the test case) follow the raster.

## 3.4.0

Phase 3: a data service. No key, lineage, area, product or evidence changes.

### Added
- r02: `docs/data_dictionary.md` / `.json`, generated from the contracts: 170 columns in 18 tables,
  each with type, nullability, unit, allowed values, meaning and the stage that writes it.
  `tests/test_release.py` fails on any released column without a contract or a meaning.
- r01: `data/release/`, byte-reproducible: 17 tables, the polygons of all 9 maps simplified per
  polygon (0.0005°, median area change 0.005%; full-resolution areas kept), `load.sql` (DuckDB
  views), `release_info.json`, `MANIFEST.csv`. Coverage simplification was measured and rejected
  (the layers' shared borders are digitised independently; it distorted Tumakuru by 26%).
- r03: read-only FastAPI service (`uvicorn district_evolution.release.api:app`): `/districts`,
  `/districts/{ck}`, `/timeline`, `/lineage`, `/geometry`, `/evidence`, `/crosswalk`, `/events`,
  `/research`, `/meta`; every response carries `pipeline_version` and `config_sha256`. p95 32 ms.
- r04: the District Ledger explorer at `/` for all 804 identities; every caption names its table row.
- Dependencies: fastapi 0.141.1, uvicorn 0.54.0, httpx 0.28.1.

## 3.3.0

Phase 2: an evidence layer. No key, lineage, area or product changes.

### Added
- Stages e01–e04. e01 turns every statement of an evidence source into a cited claim (1,771 from
  the frozen 2026-09-23 Wikidata snapshot). e02 locates each claim's subject by coordinate on the
  map of its date (633 subjects linked by geometry and name, 161 by geometry only, 28 without a
  coordinate). e03 gives each claim a verdict: 1,213 agree, 105 explained, 214 conflict, 239 not
  checkable. e04 gathers 395 open research questions.
- `data/reference/research_findings.csv`: the curated register that closes research questions
  (3 settled findings). Checks V21 (claim linked to an unknown key, ERROR), V22 (open questions,
  INFO), V23 (finding pointing at a vanished question, WARNING). 29 contracts (was 25).
- The external audit and e03 share one set of verdict rules (`evidence/rules.py`); the audit
  output is byte-identical after the refactor. Evidence thresholds moved to `config/pipeline.yaml`.

### Not done (by decision)
- DataMeet boundaries, Census District Handbooks and gazettes: no files yet (the owner will provide
  them). Each plugs in as an `EvidenceSource` (or a `BoundarySource` for audit) without core changes.

## 3.2.0

OD-01 decided: a district that is absorbed and later restored keeps a new key and gains a
`RECONSTITUTED_FROM` lineage edge. No key, product or area changes.

### Added
- s05 writes `RECONSTITUTED_FROM` when a closed identity with no lineage successor (absorbed into
  existing districts) returns as a new identity at least one map later that is mostly its land
  (`lineage.reconstitution_share`). Two edges: Fatehgarh Sahib 1951 → 2001, Barnala 1951 → 2011.
  `district_relationship` 631 → 633; baselines in `tests/baselines/v3.2.0.yaml`.

## 3.1.0

No canonical key, product or data output changed. One gate result changed: V18 has no
findings (was Manipur 1971: 4/5), explained below; baselines in `tests/baselines/v3.1.0.yaml`.

### Changed
- Code moved into the `district_evolution` package (`core`, `contracts`, `stages`, `sources`,
  `evidence`); stages run as `python -m district_evolution.stages.<stage>`. Install with
  `pip install -e . --no-deps`. Proven byte-identical on every deterministic output.
- s01 reads maps through `BoundarySource` adapters checked against a new `boundary_layer` contract.
- The V5 output manifest is built from the outputs declared in `dvc.yaml` (36 data outputs); it
  previously globbed directories and had picked up 25 stale copies. Silver layers are declared
  one file each. The copies come from iCloud Drive syncing the working folder: it duplicates
  files rewritten mid-sync as "<name> 2.<ext>".
- The Wikidata external audit is a DVC stage (`a01_external_audit`), so its outputs are rebuilt
  and hash-tracked with everything else.
- The s08 splink model JSON and the s03 GeoPackage are now byte-reproducible (random linker id
  dropped and floats rounded to 12 decimals; fixed GeoPackage timestamp). The DuckDB warehouse is
  the one output allowed to differ between builds, with its reason in `config/pipeline.yaml`.

### Added
- Check V20 (ERROR): a file under `data/silver`, `data/gold`, `data/products` or `outputs/` that no
  stage declares and git does not track.
- Regression baselines (`tests/baselines/v<version>.yaml`), CI comparing two full builds
  (`district_evolution/compare_builds.py`), a tag-triggered release workflow for Zenodo.

### Removed
- `official_district_area_benchmark.csv` (circular: SOI 2025 recomputed in a planar projection,
  finding F14), two unused v1 files under `data/silver/`, and the dead `sliver_threshold_km2`.

### Fixed
- The map-date rule (V18, external audit) read RENAME rows and parent-continuation rows as
  creations. Manipur's 1971 layer shows exactly the five districts created in 1969; four were
  renamed in 1981. Renames now inherit the original creation year, and a creation dated after an
  identity closed is treated as a later homonym. Districts shown before creation: 20 → 7.
  Evidence: `outputs/research/V18_manipur_1971.md`.
- The committed external audit report predated the confirmed Assam 1981 depiction row.

### Documented, not implemented
- OD-01 decision memo with measured evidence: `docs/decisions/OD-01_reclassification.md`.
- DVC remote and history rewrite runbook: `docs/operations/data_storage.md`.

## 3.0.0

Design and measured rationale: `docs/architecture/REVAMP_PLAN_V3.md`.

### Breaking
- **Canonical keys renumbered** (1,376 → 804). Identity now follows core-territory
  continuity instead of the symmetric 90/90 rule, which re-keyed every district that
  lost or gained more than 10% of its territory (Kangra had 6 keys). Every v2 key maps to its
  v3 key in `data/reference/ck_migration_v2_to_v3.csv` (448 identical, 923 merged into
  their continuation, 5 retired as non-administrative placeholders).
- **Event IDs changed.** A carve-out recorded twice in the events CSV (as NEW_DISTRICT and
  as SPLIT) is now one event (935 → 609 events; `recorded_as` keeps the original types).
- **Products replaced.** `district_census_area_matrix_backfilled` (mixed two meanings of
  area in one column) is replaced by `district_area_admin`, `crosswalk_to_reference`
  and `district_reference_context`.
- **Stages renumbered** into dependency order (s01–s12); s8 and s10b retired, s10
  rewritten as s09.

### Fixed
- Five unnamed placeholder polygons (including the ~80,520 km² and ~108,672 km²
  claimed-territory polygons in J&K) had received canonical keys; now excluded.
- Name normalization ignored `_`, so 212 of 468 state names in the 1991 layer never matched.
- Layers were not exact partitions (57–124 km² self-overlap per layer; Puducherry
  enclaves double counted in 2011). Overlaps now go to the enclave and are logged.
- Boundary displacement between independently digitized editions (~90,000 km²) was
  counted as territorial transfer; now its own class.
- Event linkage re-derived identity from name strings and ignored lineage; now uses a
  footprint-constrained probabilistic model. Residual "recovery" (non-deterministic,
  candidate pool limited to the event's own participants) removed: accounting follows
  the overlay partition exactly.
- Reported event transfer area exceeded India's area (retained area counted, events
  double counted); now split by role, with identifiability status per event.
- Runs were not deterministic (set-order tie-breaking); now byte-identical (V5).

### Added
- `requirements.txt` (pinned), `config/pipeline.yaml` (every threshold with rationale).
- Reference data: `state_lineage.csv`, `name_aliases.csv` (renames only; splits are not aliases).
- splink event linkage (s08), networkx lineage DAG (s05), pandera data contracts,
  DuckDB + spatial warehouse with enforced DDL and SQL invariants (s11), validation
  gate (s12), DVC pipeline (`dvc.yaml`), CI workflow, CITATION.cff, tests with golden
  historical cases.

## 2.0.0

Transition-matrix rebuild of the spatial core (planar overlay, deterministic IDs,
continuity-based identity, event-grain aggregation). See git history.

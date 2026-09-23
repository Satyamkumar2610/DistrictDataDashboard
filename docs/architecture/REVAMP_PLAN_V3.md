# District Evolution — Architecture Revamp Plan (v3)

Status: **implemented** (v3.0.0; gate PASS; see §7 for measured results) · Supersedes pipeline v2.0.0
Basis: full re-run of the v2 pipeline on 2026-09-23 (3 min 29 s, exit 0), plus measurements taken
directly from the silver geometry, gold tables, and outputs. Every number below was measured, not
estimated.

---

## 1. What v3 must deliver

For every Indian district, 1951–2025, the pipeline must answer four questions: identity, origin,
fate, and quantity. Each answer must come with a traceable evidence chain and a stated uncertainty.
The downstream use is harmonization: restating statistics reported on one census's districts onto
another census's districts.

v2 got the spatial primitive right. Its planar overlay conserves area by construction, the layer
topology is clean, and ledger closure is 99.97%. But four layers built on top of that primitive are
wrong: identity, event linkage, event accounting, and the headline area table. And none of v2's
guarantees were enforced as code. They existed only as sentences in reports.

v3 keeps the primitive, fixes the layers built on it, and turns every guarantee into a check that
can fail.

## 2. Evidence base: what the v2 re-run showed

| # | Finding | Measured | Severity |
|---|---|---|---|
| F1 | **Identity breaks whenever a district changes more than 10%.** s5 keeps a CK only if 90% of the territory carries over *in both directions*. A district that loses 11% to a carve-out, or gains 11% from a neighbour, gets a new CK. The architecture spec says the CK stays open in both cases. | 634 CK closures. About 385 are carve-out parents that kept most of their territory (≥50% to one successor, and that successor is ≥90% made of them). About 144 more kept ≥90% of their territory but gained land. Kangra has **6 CKs**, Hoshangabad 3, Durg 3. 310 names are spread across ≥2 CKs. | Critical |
| F2 | **Lineage is inflated as a result.** Edges between fragments of the same district are classified as splits and merges. | 1,058 `MERGED_INTO` edges. Real district mergers in India are rare. | Critical |
| F3 | **Name normalization ignores underscores.** Stanford 1991 writes `Himachal_Pradesh` and Stanford 1961 writes `Pashchimi_Singhbhum`. | 212 of 468 state names in 1991, plus 41 + 11 district names, can never match their spaced form. | High |
| F4 | **The state-scoped name lookup compares incompatible state labels.** The events CSV files events under modern states (Kangra → Himachal Pradesh). The early map layers label districts with historical states (Kangra → Punjab in 1951/61). s3 also copies the event's state onto every participant. So the (state, name) lookup misses, the nationwide fallback fails on homonyms, and the event gets a 100% residual by construction. | All 94 "unresolved" events show a 100.0% initial residual. | High |
| F5 | **s10 re-derives identity from name strings.** `ck_transitions` and `district_relationship` are loaded and never used. | grep-confirmed: dead after load | High |
| F6 | **s10 "recovery" is a placeholder, and it is non-deterministic.** Candidates are the event's own successors, `shared_boundary=0.5` is hardcoded, and a tie at score 0.900 is broken by Python `set` order. | Rerunning v2 reassigned residuals to different districts (Gopalganj→Siwan, Jalna→Aurangabad, Ratnagiri→Sindhudurg). | High |
| F7 | **s10 "measured transfer" includes retained area and double-counts area across events.** | 3.33M km² reported as transferred, which is more than India's total area | High |
| F8 | **Boundary displacement is counted as territorial transfer.** Two independently digitized editions don't line up, and the resulting strips pass the area-only sliver filter. | 2001→2011: 3,038 off-core pieces, mostly 0.1–1 km wide, about 53k km². 2021→2025: 2,326 pieces, most narrower than 0.3 km. Same-edition windows (1951→61, 1981→91): 45 and 17 pieces, all ≥3 km wide, meaning real transfers. The 7,233 "measured transfers" are mostly this noise. | High |
| F9 | **The s11 area table uses two meanings of "area" in one column.** `DIRECT` means the district's legal extent then. `LINEAGE_BACKFILL` means the land later occupied by the 2025 district. | Belgaum's 1951 value includes about 990 km² that is also counted in Kolhapur's 1951 value. Column totals miss the mapped India total by −5k to −90k km². | High |
| F10 | **The s10b alias table records splits as aliases.** Malabar→Kozhikode, Nimar→Khandwa, 24 Parganas→South 24 Parganas, and Bangalore→Bengaluru Urban hand a whole parent's identity to a single child. It also mixes genuine renames with state moves. | 60 entries, about 10 of them are split-as-alias | Medium |
| F11 | **Some outputs cannot be reproduced.** Nothing produces s11's input `district_census_area_matrix.csv`. s11 is missing from `run_all.sh`. There is no dependency manifest, and `tabulate` was an undeclared dependency. | The pipeline failed in a fresh environment until it was fixed by hand. | Medium |
| F12 | **Guarantees are prose, not code.** "Byte-identical reruns", "742 CKs match", and "DAG acyclic" are printed claims. `sql/`, the DDL, and the invariants were never built. | F6 disproves the reproducibility claim | Medium |
| F13 | **The tests don't test the pipeline.** Most s10b tests compute the expected status inside the test itself, so they cannot fail. | 36/37 pass. The one that fails checks a file layout. | Medium |
| F14 | **The benchmarks are circular.** `official_district_area_benchmark.csv` is SOI 2025 recomputed in a planar LCC projection. Morbi is 4,791 km² there against 4,981 km² geodesic. That projection distortion *is* the "3.7% method drift" noted in the old audit. `historical_area_benchmark.csv` is all placeholders. | No independent validation exists | Medium |
| F15 | **s10 performance.** It re-reads a full silver GeoParquet per predecessor per event. | Most of the 3.5-minute runtime | Low |
| F16 | **Unnamed placeholder polygons received CKs.** The sentinel filter missed null names (read as the string `"None"`), so the 80,520 km² and 108,672 km² J&K claimed-territory polygons (1981–2011) and the Rann of Kutch strip became "districts". | 5 v2 CKs; v2's report said they were excluded | High |
| F17 | **The events CSV records most carve-outs twice**, once as NEW_DISTRICT (parent → child) and once as SPLIT (parent → parent + child), with the same parent and year. | 313 of 364 multi-event predecessor-windows are exactly this pair. It doubled the declared transfer area and made 763 of 935 events look unidentifiable. | High |
| F18 | **Layers are not exact partitions.** Neighbouring polygons overlap along digitized edges, and in 2011 the Tamil Nadu districts were never cut around the Puducherry enclaves. | 57–124 km² of self-overlap per layer; Puducherry is counted twice and breaks overlay closure by 1.1–1.9% | Medium |

What v2 got right, and v3 keeps unchanged: the planar overlay transition matrix (V3 closure,
max error 1.13 km²), clean layer topology (0–0.0038% self-overlap), deterministic sha256 IDs, one
geodesic area method, and the event-grain aggregation (1,550 rows → 935 events).

### Root causes

- **RC-A: continuity was defined symmetrically and strictly.** Identity only needs to answer "does
  this district's core continue?" The 90/90 rule instead answers "is this district nearly
  unchanged?" That one choice produces F1, F2, part of F4/F5, and the lineage chains s11 has to walk.
- **RC-B: event names are linked to districts with deterministic string equality and no spatial
  constraint.** That produces F3, F4, F5, F6, F10, and the entire s10b repair layer.
- **RC-C: products are defined by code paths, not by stated semantics.** That produces F7, F8, F9,
  and F11.
- **RC-D: guarantees live in prose.** That produces F6's invisibility, F12, F13, and F14.

## 3. Target architecture

### 3.1 Principles (additions to Architecture v0.3 §2)

1. **Identity means the core continues.** A CK continues when a district's core territory continues,
   not only when the district is nearly unchanged.
2. **Geometry constrains, names discriminate.** Every event-name resolution is limited to the
   districts that actually exchanged territory. Within that set, a calibrated probabilistic model
   picks the name.
3. **Every product has a one-sentence meaning.** A product that mixes two meanings is split into two
   products.
4. **Every guarantee is executable.** It is a schema, a SQL constraint, an invariant query, or a
   test, and it runs on every build. A failed ERROR-level check stops the pipeline.
5. **Every piece of territory gets exactly one classification** (CORE, TRANSFER,
   BOUNDARY_DISPLACEMENT, SLIVER, LOST, or GAINED), and every classification has a configured
   threshold with a stated rationale.

### 3.2 Stage DAG

Geometry stages run first. Events enter only after identity and lineage are fixed, so the
dependency order itself enforces "events are evidence".

```
bronze ──► s01 silver ──► s02 topology ──► s03 transition matrix ──► s04 identity ──► s05 lineage ──► s06 ledger
                                              (adjacent + ref 2025)      (banded)       (networkx DAG)
events CSV ──► s07 event grain ──► s08 event linkage (splink) ──► s09 event reconciliation ◄── s03/s04/s05
                                                                                 │
                              s10 census products ◄── s03 ref overlays, s04      │
                                        │                                        │
                                        └──────► s11 DuckDB warehouse ◄──────────┘
                                                        │
                                                 s12 validation gate (exit ≠ 0 on ERROR)
```

| Stage | v3 script | Replaces | Key change |
|---|---|---|---|
| s01 | `s01_bronze_to_silver.py` | s1 | Underscore-safe normalization; null-name placeholders excluded; each layer repaired into an exact partition (overlap goes to the enclave, logged) |
| s02 | `s02_topology_audit.py` | s2 | unchanged |
| s03 | `s03_transition_matrix.py` | s4 | Parcel classes (CORE / TRANSFER / BOUNDARY_DISPLACEMENT / SLIVER); adds direct overlays of each vintage onto the 2025 reference |
| s04 | `s04_identity.py` | s5 | Banded continuity rule (§3.3); deterministic ordering; `ck_migration` from v2 |
| s05 | `s05_lineage.py` | s6 | networkx DAG, validated for acyclicity; displacement excluded from transfers; event corroboration moved to s09 |
| s06 | `s06_area_ledger.py` | s7 | Adds a displacement column to closure |
| s07 | `s07_events_aggregate.py` | s3 | Carve-outs recorded twice (NEW_DISTRICT + SPLIT) become one event; event state is evidence, not a join key |
| s08 | `s08_event_linkage.py` | name logic in s10/s10b | **splink** Fellegi-Sunter model: participant names → CK name records |
| s09 | `s09_event_reconciliation.py` | s8, s10, s10b | Linkage restricted to districts that exchanged territory; exact partition accounting; identifiability rule |
| s10 | `s10_census_products.py` | s11 + orphaned matrix script | Three products, each with one meaning (§3.5) |
| s11 | `s11_warehouse.py` | (never built) | **DuckDB + spatial**; DDL constraints; SQL invariants; independent area cross-check |
| s12 | `s12_validate.py` | s9 | **pandera** + warehouse invariants; blocking gate; report |

Retired: `s8_event_area_accounting.py`, `s10b_spatial_successor_discovery.py` (2,127 lines), and the
L1–L5 recovery hierarchy. Once linkage is limited to the districts that exchanged territory and
accounting follows the partition exactly, the residuals they existed to patch no longer occur.

### 3.3 Identity rule (s04)

For window a→b, let M be the non-sliver overlay area. Let r = M[i,j]/area(i) (the share of i that
went to j) and h = M[i,j]/area(j) (the share of j that came from i).

1. **The geometry is unambiguous.** i's largest recipient j holds r ≥ 0.90 of i, and i supplies
   most of j (h ≥ 0.50). Then i continues as j, whatever the name. A name change here is a
   rename: 148 such cases, e.g. Poona → Pune, Kolaba → Raigad, Bhilsa → Vidisha.
   - `STRONG` if h ≥ 0.90
   - `ABSORPTION_CORE` if 0.50 ≤ h < 0.90
2. **The geometry is ambiguous (i was divided).** The candidates are the children built mostly
   from i (h ≥ 0.50) that hold r ≥ 0.15 of i. The candidate that **carries i's name** continues
   i. Geometry alone can't say which child is the parent: in 1971, Jhansi went 49.9% to Jhansi
   and 50.04% to Lalitpur.
   - `CARVE_OUT_CORE` if r ≥ 0.50
   - `NAME_RETAINED_CORE` if r < 0.50
   - `REORGANISED_CORE` if h < 0.90
3. **Otherwise i closes.**
   - `BREAK_NAME_DIFFERS`: children exist, but none carries i's name. These are clean splits:
     Malabar 1957, 24 Parganas 1986, Andaman & Nicobar 1974.
   - `BREAK_NO_CORE`: no child is built mostly from i (merged or dissolved).

**Names agree** means one of the following: the names are equal; they are a documentary alias
pair; or their best Jaro-Winkler similarity is ≥ 0.90 over the raw, alias-canonical, and
word-order-insensitive forms. There is one exception. A name that is the parent's name plus a
directional qualifier ("South 24 Parganas", "Purba Bardhaman", "Bangalore Urban") marks a *derived*
new district, not the parent continuing.

Calibration on the data:
- The name_retained threshold was lowered from 0.30 to 0.15. Every same-named child lying wholly
  inside its parent with 0.16 ≤ r < 0.30 is a known multi-way carve-out continuation: Darbhanga
  1972; Adilabad, Medak, Karimnagar and Khammam in Telangana 2016; Durg, Raipur and Surguja in
  Chhattisgarh 2012.
- Because h ≥ 0.50 is required, each target continues at most one source, so continuity is a
  one-to-one matching. The code asserts this.

Thresholds live in `config/pipeline.yaml`.

**Migration.** CK numbers change. `data/reference/ck_migration_v2_to_v3.csv` maps every v2 CK to its
v3 CK through shared geometry observations, so no v2 key becomes unresolvable (invariant I-2).

### 3.4 Event linkage and reconciliation (s08–s09)

- **s08, splink.** Left side: distinct (name, recorded state) pairs from event participants. Right
  side: (CK, vintage, name, state) records from silver. Name comparison levels: exact / documentary
  alias / JW ≥ 0.95 / ≥ 0.88 / ≥ 0.80 / else. State comparison levels: exact / historically
  compatible via `state_lineage` / else. Priors are estimated with deterministic rules, u by seeded
  random sampling, and m by EM. The model's parameters are written to
  `outputs/events/splink_model.json` so reviewers can inspect them.
- **s09, choosing the window.** The candidate windows are:
  - the adjacent window containing the event year;
  - the window starting at the event year, when that year is itself a map vintage (that year's map
    may or may not show the change);
  - one lagged window, to allow for mapping delay.

  The window whose maps link the most declared participants wins, with ties going to the earliest.
- **s09, restricting to districts that exchanged territory.** Predecessors are linked at the
  window's first vintage. The eligible successors are then only the CKs that received material
  territory from those predecessors in that window (s05 `ck_flow`). The declared successor's name
  is matched only within that set. A good name match outside the set is reported as
  `OUTSIDE_FOOTPRINT` and never accepted.
- **Accounting.** Each predecessor's area splits exactly along the partition into
  `declared_successor + retained + undeclared_neighbour + boundary_displacement + lost + sliver`.
  Nothing is "recovered": every square kilometre already has a named destination.
- **Identifiability** (redesign §4.5). A row is `MEASURED` only if it is the only event touching that
  predecessor in that window. Otherwise it is `UNIDENTIFIED_MULTI_EVENT_WINDOW`, and the window total
  is reported as an upper bound.
- **Lineage corroboration.** An event whose linked (predecessor, successor) pair matches a
  `district_relationship` edge in the same window corroborates that edge. This is written to a
  separate table, so geometry-derived lineage is never modified by event data.

### 3.5 Census products (s10): one meaning each

| Product | Meaning of one row/cell | Grain |
|---|---|---|
| `district_area_admin` (+ `_wide.csv`) | Area of the administrative district as it existed at census year Y | CK × vintage |
| `crosswalk_to_reference` | km² of district i (year Y) that lies inside 2025 district j | (Y, i, j), from a **direct** Y→2025 overlay, so no Markov chaining |
| `district_reference_context` (+ `_wide.csv`) | For each 2025 district and each year Y: the district(s) that contained its land, with shares and the container's area | 742 × 9 |

This replaces the mixed-meaning backfill. The crosswalk is exact where both maps exist: no
uniform-distribution assumption, and no composition error. It is also the input
`statistical_crosswalk` needs.

### 3.6 Technology stack

| Concern | Tool | What it enforces or replaces |
|---|---|---|
| Environment | `requirements.txt` (pinned), `.venv` | F11: a fresh machine reproduces the run |
| Record linkage | **splink 4** (Fellegi-Sunter, DuckDB backend) | Replaces hardcoded JW thresholds and alias dicts with calibrated m/u probabilities (RC-B) |
| Lineage graph | **networkx** | DAG acyclicity (`is_directed_acyclic_graph`, `find_cycle`), ancestry (`s05_district_ancestry.csv`) |
| Data contracts | **pandera** | Schema, dtype, nullability, range, and uniqueness checks at every gold/product write |
| Warehouse | **DuckDB + spatial** | Real PK/UNIQUE/CHECK/FK DDL; SQL invariant queries; `ST_Area_Spheroid` as an **independent** check on the pyproj areas (verified to agree to <0.001 km²) |
| Pipeline DAG | **DVC** (`dvc.yaml`, `dvc.lock`) | Dependency-tracked `dvc repro`, and content hashes of every input and output for provenance |
| CI | GitHub Actions | pytest, full pipeline, and validation gate on every push; reports uploaded as artifacts |
| Citability | `CITATION.cff`, `CHANGELOG.md`, semver `pipeline_version` | Needed before a Zenodo DOI |

### 3.7 Configuration

All thresholds move to `config/pipeline.yaml`, each with a rationale:

| Key | Value | Rationale |
|---|---|---|
| `sliver_abs_km2` / `sliver_rel_fraction` | 0.5 / 0.0001 | Unchanged from v2; floating-point and snapping noise |
| `displacement_width_km` | 1.0 | Positional accuracy of 1:1,000,000-scale source maps. Same-edition real transfers measured ≥ 3 km wide; cross-edition jitter peaks at 0.1–0.6 km |
| `identity.strong` / `core` / `name_retained` | 0.90 / 0.50 / 0.15 | §3.3 (name_retained calibrated on the data) |
| `identity.name_jw` | 0.90 | Tie-break only |
| `linkage.min_match_probability` / `ambiguity_margin` | 0.50 / 0.10 | Accept the best candidate above 0.5; flag it if the runner-up is within 0.1 |
| `linkage.state_mismatch_m_floor` | 0.01 | EM estimates m = 0 for "incompatible state", which would make a mis-filed state an absolute veto |
| `closure.error_pct` | 1.0 | Closure excess above this share of a polygon means the overlay is broken (ERROR) |
| `closure_tol_km2` / `closure_tol_pct` | 2.0 / 0.15 | Unchanged from v2 (measured summation noise) |

## 4. Validation that can fail (s11 + s12)

| ID | Check | Where | Severity |
|---|---|---|---|
| V1 | Per-layer self-overlap < 0.1% | s02 | ERROR |
| V3 | Row closure of every transition and crosswalk: Σ flows + lost + sliver = area | s03, SQL | ERROR |
| V4 | pyproj geodesic area vs DuckDB `ST_Area_Spheroid`, ≤ 0.01% | SQL | ERROR |
| V5 | Determinism: two runs produce identical content hashes | CI (`dvc.lock` diff) | ERROR |
| V7 | Each CK's observations cover contiguous vintages (emulates the exclusion constraint) | SQL | ERROR |
| V8 | `MEASURED` only when exactly one event touches that predecessor in that window | SQL | ERROR |
| V9 | No lineage edge into a CK that already existed (L-3) | SQL | ERROR |
| V10 | Lineage graph is acyclic | networkx + recursive CTE | ERROR |
| V11 | Every gold/product table passes its pandera schema | pandera | ERROR |
| V12 | Event total transferred area ≤ Σ predecessor area | SQL | ERROR |
| V13 | 2025 active CK count equals the number of SOI 2025 features | SQL | ERROR |
| V14 | Event/geometry agreement rate, linkage rate, and match-probability distribution | report | INFO |

## 5. Phases and acceptance criteria

| Phase | Work | Done when |
|---|---|---|
| P0 | `requirements.txt`, `config/pipeline.yaml`, reference tables (`state_lineage`, `name_aliases`), underscore fix | Fresh venv runs; config drives every threshold |
| P1 | s03 parcel classes + reference overlays | V3 passes; displacement is reported separately |
| P2 | s04 banded identity + migration | Kangra, Hoshangabad, Durg, and Nellore each have **1 CK**; `MERGED_INTO` count drops sharply; every v2 CK maps to a v3 CK |
| P3 | s05 networkx lineage, s06 ledger | V9 and V10 pass; ledger closure ≥ 99.9% |
| P4 | s07 fix, s08 splink, s09 reconciliation | 0 events with a residual that is "100% by construction"; runs are deterministic; V8 and V12 pass |
| P5 | s10 products | Crosswalk closure passes; no mixed-meaning columns |
| P6 | s11 DuckDB warehouse, s12 gate, pandera schemas | Every ERROR check is executable; the gate returns non-zero on violation |
| P7 | Tests, DVC, CI, CITATION.cff, CHANGELOG | pytest tests pipeline logic on synthetic fixtures; `dvc repro` reproduces; CI workflow is valid |

## 6. Deliberately out of scope (decisions for the project owner)

- **DVC remote and removing bronze from git history.** DVC is set up locally. Moving the 238 MB of
  bronze GPKGs out of git and rewriting history to reclaim the 691 MB `.git` needs a chosen remote
  (S3 / GDrive) and a force-push that coordinates with collaborators.
- **Publishing.** The Zenodo DOI and pushing the CI workflow need the owner's accounts.
- **Independent ground truth (next phase).** Census District Handbook areas and formation dates,
  Wikidata P1365/P1366 successor claims, DataMeet boundaries as a third geometry source, and gazette
  extraction. v3 is built so that each can be added as a corroboration source without changing the
  core.
- **OD-01** (reclassification CK rule) stays open. §3.3 turns it into a threshold question.

## 7. Results (measured, v2.0.0 → v3.0.0)

Both runs used the same bronze inputs. v3 was built end to end by `run_all.sh` in 3 min 27 s,
with the validation gate passing.

| Measure | v2 | v3 |
|---|---|---|
| Canonical keys / closed identities | 1,376 / 634 | **804 / 62** |
| Names spread over ≥ 2 CKs | 310 | 36 (mostly true homonyms: Bilaspur, Hamirpur, Pratapgarh, Aurangabad; Delhi's 2012 districts) |
| Kangra / Hoshangabad / Durg / Jhansi CKs | 6 / 3 / 3 / 2 | **1 / 1 / 1 / 1** (each 1951–2025) |
| Lineage edges | 2,598 | 631 |
| `MERGED_INTO` edges | 1,058 | 3 (all Champhai 2021→25: SOI 2025 has not drawn Mizoram's 2019 districts) |
| Lineage edges corroborated by an event | 21.9% | **66.6%** (420 / 631) |
| Territorial transfers between existing districts | 7,233 | 1,358 (boundary displacement, 90,092 km², reported separately) |
| Layer self-overlap | 57–124 km² per layer | **0** (all 9 layers exact partitions) |
| Overlay closure errors > 1% of a polygon | 3 (Puducherry) | **0** |
| Administrative events | 935 (326 double-recorded) | 609 |
| Events whose transfer is identified (MEASURED) | not reported | 403 (66%); 184 share a window and are reported as a bound |
| Events with an unexplained residual that needed "recovery" | 94 (+517 placeholder recoveries) | **0**: every km² has a named destination (declared successor, retained, undeclared neighbour, displacement, sliver, unmapped) |
| Reported event transfer total | 3.33M km² (more than India's area) | 1.51M km² over events; 1.34M km² of unique flows |
| pyproj vs independent DuckDB geodesic area | not tested | max 0.0067% over 4,614 polygons |
| Determinism | not deterministic (residuals reassigned between runs) | **36 / 36 outputs byte-identical across runs** |
| Executable checks | 0 gates | 13 SQL invariants, 25 data contracts, 46 tests incl. golden history |

**Research queue produced by v3.** These are cases where the events compilation and the maps
disagree, and each needs a documentary check rather than an automatic fix. There are 54
successors whose name matches only outside the named parent's footprint. Examples:
- Tinsukia is present on the 1981 map, formed from Lakhimpur, while the CSV says it was carved
  from Dibrugarh in 1989.
- Firozabad's territory is 100% from Mainpuri on the maps, while the CSV says Agra.

The full list is in `outputs/pipeline/s12_validation_report.md`.

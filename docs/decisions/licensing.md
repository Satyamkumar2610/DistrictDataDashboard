# Licensing of the sources — blocks the open release (WP5)

Status: **decision needed from the project owner.** Found 2026-09-30 while preparing WP5.

## What the sources allow

| Source | Used for | Terms found | Verified from |
|---|---|---|---|
| Stanford "District Boundaries of India" 1951–2021 (8 layers) | Every map before 2025 | "These data are licensed by Stanford Libraries and are available to Stanford University affiliates only. [...] These data may not be reproduced or used for any purpose without permission." Publisher and copyright holder: ML InfoMap. | Catalogue records for [1951](https://searchworks.stanford.edu/view/tf374bd2484) and [2011](https://earthworks.stanford.edu/catalog/stanford-nz176rm8192) (640 districts, 29 states, 6 UTs: our 2011 layer). The other six years are assumed to carry the same terms (same series and publisher); not yet checked one by one. |
| Survey of India district boundaries, 2025 | The reference map | Free download (₹0) from the [SOI Online Maps Portal](https://onlinemaps.surveyofindia.gov.in/Digital_Product_Show.aspx). Secondary summaries report conditions accepted at download: attribution, no resale, and no sharing with foreign individuals or entities. | The portal page shows no terms; **the declaration accepted at download must be read and recorded.** |
| Events compilation (`district_evolution_master.csv`) | Event dates and names | Unknown: its `source` column names three Google Drive file IDs. | Provenance to be documented. |
| Wikidata snapshot (2026-09-23) | External audit and evidence | CC0 (Wikidata's licence). Free to redistribute. | Wikidata terms. |

## What this means for the project

1. **The public GitHub repository already redistributes the Stanford files** (`data/bronze/stanford`,
   committed in git history). The repository is public (checked via the GitHub API on 2026-09-30).
   Under the terms above this needs the publisher's permission.
2. **The release (r01)** ships the polygons of all nine maps (simplified) and tables derived from
   them. A Zenodo archive of the repository would also include the bronze files and their history.
3. **The API and explorer** serve those polygons.
4. Derived numbers (areas, crosswalk shares, lineage) are computed from the licensed polygons;
   whether they may be published without the polygons is a question for the licensor.

Nothing in the pipeline's method depends on this; it decides only what may be published.

## Options

- **A. Ask ML InfoMap (and confirm the SOI declaration) for permission** to redistribute the
  layers, or at least derived products, under a stated licence. Contact given in the Stanford
  records: the publisher, ML InfoMap. Best outcome; keeps the plan unchanged.
- **B. Publish only what the sources allow**: code (any licence you choose), the Wikidata
  evidence, and the methods; keep the geometry and derived tables private until permission.
  The release and Zenodo archive exclude `data/`.
- **C. Replace the restricted maps with openly licensed ones** where they exist (e.g. community
  district boundaries under an open licence), re-running the pipeline on them. This changes the
  evidence base and needs its own evaluation per `docs/sources/README.md`.

## Immediate step, whatever the choice

Consider making the GitHub repository private until this is settled, and do not tag a release
(the release workflow would publish to Zenodo once it is enabled). Removing the files from public
history needs the history rewrite in `docs/operations/data_storage.md`.

Recommendation: A, with B in force until an answer arrives. Code can be opened now under a
permissive licence (MIT or Apache-2.0); data licensing waits for the licensors.

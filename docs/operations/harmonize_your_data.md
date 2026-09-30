# Harmonize your own data

Restate district statistics reported on any census-era map (1951–2021) onto the 2025 districts,
without adding them to `config/indicators.yaml` or rebuilding. Three ways in, one engine
(`district_evolution/harmonize/restate.py`, which runs h01–h03's `link` and `allocate` against the
release tables):

| Way | How |
|---|---|
| Web | the **Harmonize** page: upload a CSV, say which column holds what, download the result and the matching report |
| Command line | `python -m district_evolution.harmonize.cli in.csv --out out.csv --name District --state State --year Year --value Production` |
| API | `POST /api/harmonize` with `{"rows": [{"name", "state", "year", "value"}], "kind", "indicator", "map_year"}` (OpenAPI at `/docs`) |

Nothing you send is stored. The API processes a request in memory and forgets it.

## What happens to each row

1. **Which map.** A value for year *y* reports on the latest map that depicts no later than *y*
   (for that state; see `data/reference/vintage_depiction.csv`). If your source says which
   boundaries it uses (e.g. "apportioned to 1991 districts"), pass that map as `map_year`.
2. **Which identity.** The name is matched to the identity that carried it on that map: the same
   state first, then historically compatible states (Madras → Tamil Nadu). An exact normalised
   name is tried first, then the identity rule's name agreement (`identity.name_jw`). A row with no
   state is matched against the whole map.
3. **Sharing out.** A linked total is shared among 2025 districts by each district's area share
   (`crosswalk_to_reference`, a direct overlay of the two maps). The AREA method assumes the
   quantity is spread evenly over the district's area.

Each row comes back with one status:

| Status | Meaning | Used? |
|---|---|---|
| `LINKED` | exactly one identity carried this name on that map | yes |
| `AMBIGUOUS` | more than one did; the candidates are listed | no |
| `UNLINKED` | none did; identities with a similar name on that map are listed (`harmonize.suggest`) | no |
| `BEFORE_FIRST_MAP` | the year is before the 1951 map | no |
| `NO_VALUE` | the value is not a number | no |

Nothing is guessed. Fix the name or state in your file and run again.

## Reading the result

- `value`: the total on each 2025 district and year.
- `n_sources`: how many reporting districts contributed.
- `coverage_score`: the share of the 2025 district's land that reporting districts covered. Below 1
  means some of its land had no reported value; nothing is imputed.
- `boundary_uncertain`: a boundary event touching a source district falls between its map and the
  reported year, so the figures may already use the newer boundaries.
- The summary compares the total reported by linked rows with the total landing on 2025 districts.
  The small difference is land of the source districts that lies outside the 2025 map's districts.

## Rates

A rate (yield, a share, per-capita figures) is refused. A district's yield is not split between its
successors. Harmonize the numerator and the denominator as totals (production and area), then
divide the harmonized results.

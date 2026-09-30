# Examples

Each example reads only the release (`data/release/`), so it works on any copy of a release, and
`tests/test_examples.py` runs all of them on every build.

| File | Shows |
|---|---|
| `01_questions.sql` | Five questions in plain SQL with DuckDB: districts per map, one district through time, the largest carve-outs, where a 1951 district's land went, Wikidata agreement |
| `02_restate_statistics.py` | Restating statistics reported on the 1971 map onto the 2025 districts |
| `03_family_tree.py` | Every ancestor and descendant of a district, with the land that moved |

```bash
(cd data/release && duckdb -c ".read load.sql" -c ".read ../../examples/01_questions.sql")
PYTHONPATH=. .venv/bin/python examples/02_restate_statistics.py
PYTHONPATH=. .venv/bin/python examples/03_family_tree.py Malabar
```

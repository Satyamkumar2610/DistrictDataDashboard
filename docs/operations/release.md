# Releasing a version (and getting a DOI)

A release is a git tag `vX.Y.Z` equal to `pipeline_version` in `config/pipeline.yaml`. The same
version must appear in `pyproject.toml` and `CITATION.cff`; `tests/test_core.py` fails if they differ.

## One-time setup (repository owner)

1. Push the repository, including `.github/workflows/`, to GitHub.
2. Sign in at https://zenodo.org with the GitHub account, open Account → GitHub, and switch the
   repository on. From then on Zenodo archives every published GitHub Release and mints a DOI.
3. Zenodo builds the record's metadata from `CITATION.cff` (title, authors, version, abstract,
   keywords). Add a `license` field to `CITATION.cff` once the licences are chosen (WP5).
4. After the first DOI is minted, add it to `CITATION.cff` as `doi:` and to the README.

## Every release

1. Update `CHANGELOG.md`. A change that renumbers canonical keys or changes a product's meaning is
   a MAJOR version and also extends the key migration map (`data/reference/ck_migration_*.csv`).
2. If any regression baseline changes, add `tests/baselines/v<new version>.yaml` and explain each
   delta in the changelog.
3. Bump the version in `config/pipeline.yaml`, `pyproject.toml` and `CITATION.cff`.
4. `git tag vX.Y.Z && git push origin vX.Y.Z`.

The `release` workflow then rebuilds from bronze, runs the validation gate and every test, and
publishes a GitHub Release whose notes are the validation report. The report, the check table, the
output hash manifest and the external audit report are attached. Zenodo picks the release up
within minutes.

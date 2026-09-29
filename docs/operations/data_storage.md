# Data storage: DVC remote and moving bronze out of git

Status: prepared, **not executed**. Choosing a remote needs the owner's account, and rewriting
history changes every commit hash, so every collaborator must re-clone afterwards.

## Why

The nine bronze GeoPackages and the events CSV are committed to git. Every clone downloads every
version of them ever committed. DVC is already set up (`dvc.yaml`, `dvc.lock`); only a remote is
missing, and until one exists all outputs are declared `cache: false`.

## Measured size (2026-09-29)

| What | Size |
|---|---|
| `data/bronze` on disk | 238 MB |
| Everything a clone of `origin/main` downloads (all reachable history, packed) | 95 MB |
| of which bronze GeoPackages and events CSV | 74 MB |
| Clone after bronze leaves history (estimate: 95 − 74) | ~21 MB |
| Local `.git` on the owner's machine | 692 MB before `git repack`, 646 MB after |

The local `.git` is large for a different reason: an August commit that added every generated file
(including a 234 MB DuckDB file and a 97 MB `district_snapshot.csv`) was undone with `git reset`,
but its objects are still referenced by the local reflog. They were never pushed and are not in
any clone. Reclaiming that space locally is `git reflog expire --expire=now --all && git gc
--prune=now`, which permanently removes the ability to recover those undone commits. Run it only
after deciding nothing in them is needed.

## Step 1: add a remote (no history change)

Pick one provider. Examples:

```bash
dvc remote add -d storage s3://<bucket>/district-evolution          # AWS S3
dvc remote add -d storage gdrive://<folder-id>                        # Google Drive
dvc remote add -d storage azure://<container>/district-evolution      # Azure Blob
dvc remote modify storage --local <credential settings>               # credentials stay out of git
```

Then track bronze with DVC instead of git and push it:

```bash
git rm -r --cached data/bronze
dvc add data/bronze/stanford data/bronze/soi data/bronze/events
git add data/bronze/*.dvc data/bronze/.gitignore
git commit -m "Track bronze with DVC"
dvc push
```

From then on, CI needs the remote credentials as repository secrets and runs `dvc pull` before
`dvc repro`. The pipeline itself does not change: stages read the same paths.

## Step 2: remove bronze from history (only with explicit approval)

This is the step that shrinks every clone. It rewrites all commits, so coordinate first: everyone
pushes their work, the rewrite is force-pushed once, and everyone re-clones.

```bash
pip install git-filter-repo
git clone --mirror https://github.com/Satyamkumar2610/architecture.git architecture-mirror
cd architecture-mirror
git filter-repo --path data/bronze --invert-paths
git push --force --mirror
```

Keep the untouched mirror as a backup until the rewritten repository is verified: rebuild with
`dvc pull && dvc repro` and compare `dvc.lock` output hashes with the pre-rewrite build
(`python -m district_evolution.compare_builds`).

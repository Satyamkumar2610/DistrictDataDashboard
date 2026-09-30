"""Where a build came from: pipeline version, config hash, source commit, Python and package versions.

Deterministic for a given checkout and environment, so two builds of the same commit record the same
provenance (the determinism check compares them byte for byte).
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
from importlib import metadata

from .config import CONFIG_DIR, PIPELINE_VERSION, PROJECT_ROOT

KEY_PACKAGES = ["pandas", "numpy", "geopandas", "shapely", "pyproj", "pyarrow", "duckdb", "splink", "pandera",
                "networkx", "fastapi"]


def source_commit() -> str | None:
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)
    return git.stdout.strip() or None


def package_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for p in KEY_PACKAGES:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            out[p] = None
    return out


def provenance() -> dict:
    return {"pipeline_version": PIPELINE_VERSION,
            "config_sha256": hashlib.sha256((CONFIG_DIR / "pipeline.yaml").read_bytes()).hexdigest(),
            "source_commit": source_commit(),
            "python": platform.python_version(),
            "packages": package_versions()}

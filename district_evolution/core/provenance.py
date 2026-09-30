"""Where a build came from: pipeline version, config hash, a hash of the pipeline's code, Python and
package versions.

Content-addressed, not commit-addressed: the same code and inputs record the same provenance whatever
the commit, so a released file's hash (dvc.lock) stays valid across commits that do not change what it
depends on. The git commit is reported by `python -m district_evolution info` and the build logs.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
from importlib import metadata

from .config import CONFIG_DIR, PIPELINE_VERSION, PROJECT_ROOT

PACKAGE_DIR = PROJECT_ROOT / "district_evolution"

KEY_PACKAGES = ["pandas", "numpy", "geopandas", "shapely", "pyproj", "pyarrow", "duckdb", "splink", "pandera",
                "networkx", "fastapi"]


def source_commit() -> str | None:
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)
    return git.stdout.strip() or None


def code_sha256() -> str:
    """sha256 over every .py file of the package (path and content, in path order)."""
    h = hashlib.sha256()
    for f in sorted(PACKAGE_DIR.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        h.update(str(f.relative_to(PROJECT_ROOT)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
    return h.hexdigest()


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
            "code_sha256": code_sha256(),
            "python": platform.python_version(),
            "packages": package_versions()}

"""Monte Carlo over boundary position: how stable are the crosswalk weights?

The crosswalk (s10) treats every boundary as exact. This perturbs BOTH layers
of one REFERENCE overlay (year Y and the reference map) with independent,
smooth random displacement fields, re-runs the s03 overlay and classification
and recomputes each (source CK, target CK) share, N times.

Why a smooth field: one field per layer moves every vertex of a shared
boundary identically, so each layer stays an exact partition (no gaps or
overlaps are created). The field is a sum of random plane waves with
wavelengths 30-300 km (boundary errors are spatially correlated), scaled so
the RMS displacement equals sigma: by default the sigma s10h measured against
census-reported areas (outputs/pipeline/s10h_area_calibration.csv).

Outputs (outputs/audit/):
  monte_carlo_crosswalk_<Y>.csv  per pair: point share, p05/p50/p95 over runs
  monte_carlo_summary_<Y>.csv    distribution of the p05-p95 width over pairs

Usage (each run is one full overlay, ~0.5-1 min for the 2011-2025 pair):
  .venv/bin/python scripts/audit/boundary_monte_carlo.py --year 2011 --runs 20 [--sigma-km 0.1] [--seed 1]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "pipeline"))
import lib  # noqa: E402
import s03_transition_matrix as s03  # noqa: E402

KM_PER_DEG = 111.32


def smooth_field(rng: np.random.Generator, sigma_km: float, n_waves: int = 24):
    """A random displacement field (dx_deg, dy_deg) = f(lon, lat), RMS = sigma_km."""
    wavelength = rng.uniform(30.0, 300.0, size=(2, n_waves))           # km
    angle = rng.uniform(0.0, 2 * np.pi, size=(2, n_waves))
    phase = rng.uniform(0.0, 2 * np.pi, size=(2, n_waves))
    kx = np.cos(angle) * 2 * np.pi / wavelength                         # rad per km
    ky = np.sin(angle) * 2 * np.pi / wavelength
    amp = sigma_km * np.sqrt(2.0 / n_waves)                             # RMS of the sum = sigma

    def apply(coords: np.ndarray) -> np.ndarray:
        lon, lat = coords[:, 0], coords[:, 1]
        xkm = lon * KM_PER_DEG * np.cos(np.radians(lat))
        ykm = lat * KM_PER_DEG
        arg = (xkm[:, None, None] * kx[None, :, :] + ykm[:, None, None] * ky[None, :, :]
               + phase[None, :, :])                                     # (n, 2 axes, waves)
        d = amp * np.sin(arg).sum(axis=2) / np.sqrt(2.0)                # (n, 2) km, per-axis RMS sigma/sqrt2
        out = coords.copy()
        out[:, 0] = lon + d[:, 0] / (KM_PER_DEG * np.cos(np.radians(lat)))
        out[:, 1] = lat + d[:, 1] / KM_PER_DEG
        return out
    return apply


def perturbed(layer: gpd.GeoDataFrame, field) -> gpd.GeoDataFrame:
    g = layer.copy()
    g["geometry"] = shapely.transform(g.geometry.values, field)
    g["geometry"] = shapely.make_valid(g.geometry.values)
    g["area_km2"] = g.geometry.apply(lib.geodesic_area_km2)
    return g


def shares(parts: pd.DataFrame, ck: dict, area: dict) -> pd.Series:
    p = parts[parts.part_class != "sliver"]
    km2 = p.groupby(["obs_a", "obs_b"]).part_km2.sum().reset_index()
    km2["source_ck"], km2["target_ck"] = km2.obs_a.map(ck), km2.obs_b.map(ck)
    km2["share"] = km2.part_km2 / km2.obs_a.map(area)
    return km2.groupby(["source_ck", "target_ck"]).share.sum()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2011)
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--sigma-km", type=float, default=None)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    if args.year == lib.REFERENCE_YEAR:
        raise SystemExit("--year must differ from the reference year")
    sigma = args.sigma_km
    if sigma is None:
        cal = pd.read_csv(lib.OUTPUT_DIR / "s10h_area_calibration.csv")
        sigma = float(cal.sigma_used_km.iloc[0])

    obs = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_observation.parquet")
    ck, area = dict(zip(obs.geom_obs_id, obs.canonical_key)), dict(zip(obs.geom_obs_id, obs.area_km2))
    a, b = s03.load(args.year), s03.load(lib.REFERENCE_YEAR)
    width = s03.displacement_width(args.year, lib.REFERENCE_YEAR)
    point = shares(s03.classify_parts(a, b, width), ck, area).rename("point")

    rng = np.random.default_rng(args.seed)
    runs = []
    for i in range(args.runs):
        pa, pb = perturbed(a, smooth_field(rng, sigma)), perturbed(b, smooth_field(rng, sigma))
        area_i = dict(zip(pa.geom_obs_id, pa.area_km2))
        runs.append(shares(s03.classify_parts(pa, pb, width), ck, area_i).rename(i))
        print(f"run {i + 1}/{args.runs}")
    m = pd.concat([point, *runs], axis=1).fillna(0.0)
    sim = m.drop(columns="point")
    out = pd.DataFrame({"point_share": m.point, "p05": sim.quantile(0.05, axis=1),
                        "p50": sim.quantile(0.50, axis=1), "p95": sim.quantile(0.95, axis=1)})
    out["width_p05_p95"] = out.p95 - out.p05
    out = out[(out.point_share > 0) | (out.p95 > 0)].reset_index()
    dest = ROOT / "outputs" / "audit"
    dest.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest / f"monte_carlo_crosswalk_{args.year}.csv", index=False)
    material = out[out.point_share >= 0.01]
    summ = pd.DataFrame([{"year": args.year, "runs": args.runs, "sigma_km": sigma, "pairs": len(out),
                          "pairs_share_ge_1pct": len(material),
                          "median_width_p05_p95": material.width_p05_p95.median(),
                          "p90_width_p05_p95": material.width_p05_p95.quantile(0.9),
                          "max_width_p05_p95": material.width_p05_p95.max()}])
    summ.to_csv(dest / f"monte_carlo_summary_{args.year}.csv", index=False)
    print(summ.round(5).to_string(index=False))


if __name__ == "__main__":
    main()

"""CROPLAND weights (WP4): exact zonal sums on synthetic rasters, and the Kangra 1951 test case.

The rasters here are synthetic and say so: no cropland raster has been supplied. They test the method,
not any statement about where crops grow.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import yaml
from shapely.geometry import box

from district_evolution import core
from district_evolution.harmonize import cropland_spec, engine, methods_for, weight_methods
from district_evolution.harmonize.cropland import CroplandRaster, CroplandWeight, zonal
from district_evolution.harmonize.indicators import CsvIndicator, MappedAreaIndicator
from district_evolution.harmonize.weights import AreaWeight

rasterio = pytest.importorskip("rasterio")
from rasterio.features import rasterize  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402

CELL = 0.01  # degrees
X0, Y0 = 77.0, 30.10  # top-left corner of the synthetic grid


def write_raster(path, data, transform, crs="EPSG:4326", nodata=-1.0):
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1], count=1,
                       dtype="float32", crs=crs, transform=transform, nodata=nodata) as ds:
        ds.write(data.astype("float32"), 1)
    return path


def layer(rects: dict) -> gpd.GeoDataFrame:
    keys = sorted(rects)
    return gpd.GeoDataFrame({"key": keys}, geometry=[box(*rects[k]) for k in keys], crs="EPSG:4326")


def row_km2(i: int) -> float:
    top = Y0 - i * CELL
    return core.geodesic_area_km2(box(0, top - CELL, CELL, top))


@pytest.fixture
def grid(tmp_path):
    """10 x 10 cells: cropland fraction 1.0 in the west half, 0.5 in the east half, one nodata cell."""
    data = np.where(np.arange(10)[None, :] < 5, 1.0, 0.5) * np.ones((10, 1))
    data[4, 7] = -1.0
    path = write_raster(tmp_path / "crop.tif", data, from_origin(X0, Y0, CELL, CELL))
    sources = layer({"W": (77.0, 30.0, 77.05, 30.1), "E": (77.05, 30.0, 77.1, 30.1)})
    # targets cover rows 2-9 only (lat 30.00-30.08): rows 0-1 lie in no 2025 district
    targets = layer({"S": (77.0, 30.0, 77.1, 30.05), "N": (77.0, 30.05, 77.1, 30.08)})
    return path, data, sources, targets


def test_cropland_is_partitioned_exactly_like_land(grid):
    path, data, sources, targets = grid
    pairs, per_source = zonal(CroplandRaster(str(path), "synthetic", "fraction"), sources, targets)
    p = pairs.set_index(["source_key", "target_key"]).cropland_km2
    expected = {}
    for i in range(10):
        tgt = None if i < 2 else ("N" if i < 5 else "S")
        for j in range(10):
            if data[i, j] < 0:
                continue
            k = ("W" if j < 5 else "E", tgt)
            expected[k] = expected.get(k, 0.0) + data[i, j] * row_km2(i)
    for (s, t), v in expected.items():
        got = pairs[(pairs.source_key == s) & (pairs.target_key.isna() if t is None else pairs.target_key == t)]
        assert got.cropland_km2.sum() == pytest.approx(v, rel=1e-12), (s, t)
    tot = per_source.set_index("source_key")
    assert tot.cropland_km2["W"] == pytest.approx(sum(row_km2(i) for i in range(10)) * 5, rel=1e-12)
    assert tot.nodata_km2.to_dict() == {"E": pytest.approx(row_km2(4)), "W": 0.0}
    assert tot.cells.to_dict() == {"E": 50, "W": 50}
    assert tot.cell_km2["W"] == pytest.approx(5 * sum(row_km2(i) for i in range(10)), rel=1e-12)
    assert pairs.groupby("source_key").cropland_km2.sum().to_dict() == pytest.approx(tot.cropland_km2.to_dict())
    assert p.index.is_unique


def test_blocks_do_not_change_the_result(grid):
    path, _, sources, targets = grid
    spec = CroplandRaster(str(path), "synthetic", "fraction")
    one = zonal(spec, sources, targets, block_rows=1024)
    small = zonal(spec, sources, targets, block_rows=3)
    for a, b in zip(one, small, strict=True):
        pd.testing.assert_frame_equal(a, b, rtol=1e-12)


def test_area_units_and_scale(grid, tmp_path):
    _, _, sources, targets = grid
    ha = write_raster(tmp_path / "ha.tif", np.full((10, 10), 5000.0), from_origin(X0, Y0, CELL, CELL))  # 50 ha a cell
    _, per = zonal(CroplandRaster(str(ha), "synthetic", "area_ha", scale=0.01), sources, targets)
    assert per.cropland_km2.tolist() == pytest.approx([50 * 0.5, 50 * 0.5])  # 0.5 km2 a cell, 50 cells each


def test_impossible_values_are_refused(grid, tmp_path):
    _, _, sources, targets = grid
    bad = write_raster(tmp_path / "bad.tif", np.full((10, 10), 100.0), from_origin(X0, Y0, CELL, CELL))  # percent
    with pytest.raises(ValueError, match=r"outside 0\.\.cell area"):
        zonal(CroplandRaster(str(bad), "synthetic", "fraction"), sources, targets)
    _, per = zonal(CroplandRaster(str(bad), "synthetic", "fraction", scale=0.01), sources, targets)
    assert per.cropland_km2.sum() == pytest.approx(sum(row_km2(i) for i in range(10)) * 10, rel=1e-12)


def test_nan_cells_and_districts_outside_the_raster(grid, tmp_path):
    """NaN counts as nodata even when the raster declares none; a district beyond the raster has no cells."""
    _, data, sources, targets = grid
    nan = data.copy()
    nan[0, 0] = np.nan
    path = tmp_path / "nan.tif"
    with rasterio.open(path, "w", driver="GTiff", height=10, width=10, count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(X0, Y0, CELL, CELL)) as ds:
        ds.write(np.where(nan < 0, 0.0, nan).astype("float32"), 1)
    far = pd.concat([sources, layer({"Z": (80.0, 20.0, 80.1, 20.1)})], ignore_index=True)
    _, per = zonal(CroplandRaster(str(path), "synthetic", "fraction"), far, targets)
    per = per.set_index("source_key")
    assert per.nodata_km2["W"] == pytest.approx(row_km2(0))
    assert (per.cells["Z"], per.cell_km2["Z"], per.cropland_km2["Z"]) == (0, 0.0, 0.0)


def test_a_projected_raster_uses_its_cell_area(tmp_path):
    """A 10 km square in UTM 43N on a 100 m grid that is cropland everywhere holds about its own area."""
    sq = gpd.GeoDataFrame({"key": ["A"]}, geometry=[box(500_000, 3_300_000, 510_000, 3_310_000)], crs="EPSG:32643")
    path = write_raster(tmp_path / "utm.tif", np.ones((120, 120)), from_origin(499_000, 3_311_000, 100, 100),
                        crs="EPSG:32643")
    _, per = zonal(CroplandRaster(str(path), "synthetic", "fraction"), sq.to_crs("EPSG:4326"), None)
    assert per.cropland_km2.iloc[0] == pytest.approx(100.0, rel=0.02)


def test_declaration_is_checked():
    with pytest.raises(ValueError, match="value must be one of"):
        CroplandRaster("x.tif", "synthetic", "percent")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="scale"):
        CroplandRaster("x.tif", "synthetic", "fraction", scale=0)
    with pytest.raises(ValueError, match="source"):
        CroplandRaster("x.tif", " ", "fraction")


def test_cropland_is_declared_in_config_or_absent(tmp_path, monkeypatch):
    assert cropland_spec() is None or cropland_spec().file.is_file()
    (tmp_path / "indicators.yaml").write_text(yaml.safe_dump({"indicators": [], "ratios": [], "weights": {
        "cropland": {"path": "data/bronze/cropland/x.tif", "source": "synthetic", "value": "fraction"}}}))
    monkeypatch.setattr(core, "CONFIG_DIR", tmp_path)
    assert sorted(weight_methods()) == ["AREA", "CROPLAND"]
    assert methods_for(MappedAreaIndicator(), ["AREA", "CROPLAND"]) == ["AREA"]
    ind = CsvIndicator(code="x", unit="t", kind="extensive", path="p", source="s", columns={})
    assert methods_for(ind, ["AREA", "CROPLAND"]) == ["AREA", "CROPLAND"]


def test_declared_inputs_are_pipeline_dependencies():
    """Supplied statistics and the raster live where h01 and h02 depend on them, so dvc repro reruns on change."""
    stages = yaml.safe_load((core.PROJECT_ROOT / "dvc.yaml").read_text())["stages"]
    assert "data/bronze/agri" in stages["h01_stat_observation"]["deps"]
    assert "data/bronze/cropland" in stages["h02_statistical_crosswalk"]["deps"]
    cfg = yaml.safe_load((core.CONFIG_DIR / "indicators.yaml").read_text()) or {}
    for spec in cfg.get("indicators") or []:
        assert spec["path"].startswith("data/bronze/agri/"), spec["code"]
    if (cfg.get("weights") or {}).get("cropland"):
        assert cfg["weights"]["cropland"]["path"].startswith("data/bronze/cropland/")


built = pytest.mark.skipif(not (core.PRODUCTS_DIR / "crosswalk_to_reference.parquet").exists()
                           or not core.silver_path(1951).exists(), reason="pipeline not built")


@built
def test_kangra_1951_area_and_cropland_weights_diverge(tmp_path):
    """The WP4 test case. Kangra 1951 (IND-000202): 46% of its land is in today's Lahaul & Spiti, a high
    cold desert. With a synthetic raster that has cropland everywhere except Lahaul & Spiti, AREA still
    sends 46% of a crop total there and CROPLAND sends none; both conserve what their weights carry."""
    reg = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key").latest_name
    lahaul = reg.index[reg == "Lahul & Spiti"][0]
    ref = gpd.read_parquet(core.silver_path(core.REFERENCE_YEAR))
    ck = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet").query("year == @core.REFERENCE_YEAR")
    lahaul_geom = ref[ref.geom_obs_id.isin(ck[ck.canonical_key == lahaul].geom_obs_id)].geometry.union_all()
    transform = from_origin(75.0, 34.0, CELL, CELL)
    shape = (300, 400)  # 75-79 E, 31-34 N
    in_lahaul = rasterize([(lahaul_geom, 1)], out_shape=shape, transform=transform, fill=0, dtype="uint8")
    path = write_raster(tmp_path / "synthetic_cropland.tif", np.where(in_lahaul == 1, 0.0, 1.0), transform)

    cropland = CroplandWeight(CroplandRaster(str(path), "synthetic test raster (not data)", "fraction"))
    wc = cropland.weights(1951).query("source_ck == 'IND-000202'").set_index("target_ck").weight
    wa = AreaWeight().weights(1951).query("source_ck == 'IND-000202'").set_index("target_ck").weight
    assert wa[lahaul] == pytest.approx(0.46, abs=0.005)
    assert wc.get(lahaul, 0.0) == 0.0
    assert wc.sum() <= 1 + 1e-12 and wc["IND-000202"] > wa["IND-000202"]  # Kangra keeps more of its crop

    obs = engine.link(pd.DataFrame({"indicator": "prod_t", "raw_name": ["Kangra"], "state": ["Punjab"], "year": [1951],
                                    "map_year": [float("nan")], "value": [100.0], "unit": "t", "source": "synthetic"}))
    by_area = engine.allocate(obs, AreaWeight().weights(1951), "extensive").set_index("target_ck").value
    by_crop = engine.allocate(obs, cropland.weights(1951), "extensive").set_index("target_ck").value
    assert by_area[lahaul] == pytest.approx(46.0, abs=0.5) and by_crop.get(lahaul, 0.0) == 0.0
    assert by_crop.sum() == pytest.approx(100.0 * wc.sum()) and by_area.sum() == pytest.approx(100.0 * wa.sum())

    cov = cropland.coverage(1951).set_index("source_ck").loc["IND-000202"]
    assert cov.allocated_cropland_km2 + cov.unallocated_cropland_km2 == pytest.approx(cov.cropland_km2)
    assert cov.nodata_km2 == 0.0


def test_method_sensitivity_flags_and_keeps_one_sided_values():
    from district_evolution.stages import h05_validate

    h = pd.DataFrame({"indicator": "x", "year": 1951, "method": ["AREA", "CROPLAND", "AREA", "CROPLAND", "AREA"],
                      "target_ck": ["IND-000001", "IND-000001", "IND-000002", "IND-000002", "IND-000003"],
                      "value": [100.0, 110.0, 100.0, 40.0, 5.0]})
    s = h05_validate.sensitivity(h).set_index("target_ck")
    assert s.flagged.to_dict() == {"IND-000001": False, "IND-000002": True, "IND-000003": True}
    assert s.rel_difference["IND-000001"] == pytest.approx(0.10) and pd.isna(s.value["IND-000003"])
    assert h05_validate.sensitivity(h[h.method == "AREA"]).empty

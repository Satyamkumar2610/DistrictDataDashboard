"""Overlay classification (s03) and layer partition repair (s01) on synthetic polygons."""

import geopandas as gpd
import lib
import pytest
import s01_bronze_to_silver as s01
import s03_transition_matrix as s03
from shapely.geometry import MultiPolygon, box


def layer(rows):
    g = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    g["area_km2"] = g.geometry.apply(lib.geodesic_area_km2)
    return g


def test_split_is_classified_core_and_conserves_area():
    a = layer([{"geom_obs_id": "A", "geometry": box(0, 0, 1, 1)}])
    b = layer([{"geom_obs_id": "B1", "geometry": box(0, 0, 0.6, 1)},
               {"geom_obs_id": "B2", "geometry": box(0.6, 0, 1, 1)}])
    parts = s03.classify_parts(a, b)
    assert set(parts.part_class) == {"core"}  # each child is wholly inside the parent
    # Geodesic edges between the new split vertices bend differently from the
    # parent's single edge, so parts sum to the whole only within the closure
    # tolerance (the same effect lib.within_closure exists for).
    total = a.area_km2.iloc[0]
    assert lib.within_closure(parts.part_km2.sum() - total, total)


def two_neighbours():
    return layer([{"geom_obs_id": "A", "geometry": box(0, 0, 1, 1)},
                  {"geom_obs_id": "C", "geometry": box(1, 0, 2, 1)}])


def test_wide_block_changing_hands_is_transfer():
    # the A/C boundary moves 0.2 degrees east: a ~22 km wide block of C joins A
    b = layer([{"geom_obs_id": "A2", "geometry": box(0, 0, 1.2, 1)},
               {"geom_obs_id": "C2", "geometry": box(1.2, 0, 2, 1)}])
    parts = s03.classify_parts(two_neighbours(), b).set_index(["obs_a", "obs_b"])
    assert parts.loc[("C", "A2"), "part_class"] == "transfer"
    assert parts.loc[("A", "A2"), "part_class"] == "core"


def test_thin_boundary_offset_is_displacement():
    # the later map draws the same boundary 0.001 degrees (~110 m) further west
    b = layer([{"geom_obs_id": "A2", "geometry": box(0, 0, 0.999, 1)},
               {"geom_obs_id": "C2", "geometry": box(0.999, 0, 2, 1)}])
    parts = s03.classify_parts(two_neighbours(), b).set_index(["obs_a", "obs_b"])
    assert parts.loc[("A", "C2"), "part_class"] == "displacement"
    assert parts.loc[("A", "C2"), "width_km"] < 1.0


def test_resolve_overlaps_gives_the_overlap_to_the_enclave():
    big, enclave = MultiPolygon([box(0, 0, 1, 1)]), MultiPolygon([box(0.4, 0.4, 0.5, 0.5)])
    areas = [lib.geodesic_area_km2(big), lib.geodesic_area_km2(enclave)]
    geoms, log = s01.resolve_overlaps([big, enclave], areas, ["BIG", "ENC"])
    assert geoms[1].equals(enclave)  # enclave untouched
    assert lib.geodesic_area_km2(geoms[0]) == pytest.approx(areas[0] - areas[1], rel=1e-6)
    assert [x["geom_obs_id"] for x in log] == ["BIG"]

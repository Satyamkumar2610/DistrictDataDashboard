"""Shared core: configuration, the one area method, deterministic IDs, names, reference tables, table writer."""

from .area import GEOD, geodesic_area_km2, geodesic_area_perimeter, within_closure
from .config import (
    CFG,
    CONFIG_DIR,
    EVENTS_CSV,
    EVENTS_OUTPUT_DIR,
    EVIDENCE_OUTPUT_DIR,
    GOLD_CORE_DIR,
    GOLD_EVENTS_DIR,
    GOLD_EVIDENCE_DIR,
    GOLD_HARMONIZE_DIR,
    GOLD_SPATIAL_DIR,
    HARMONIZE_OUTPUT_DIR,
    OUTPUT_DIR,
    PIPELINE_VERSION,
    PRODUCTS_DIR,
    PROJECT_ROOT,
    REFERENCE_DIR,
    REFERENCE_YEAR,
    RELEASE_DIR,
    SILVER_GEOM_DIR,
    SOURCE_BY_YEAR,
    VINTAGES,
    WAREHOUSE_PATH,
    WINDOWS,
    YEARS,
    silver_path,
)
from .ids import stable_id
from .io import write_table
from .names import (
    PC11_STATE_CODES,
    QUALIFIERS,
    STATE_SPELLINGS,
    alias_key,
    canonical_state,
    display_name,
    is_qualified_derivative,
    jaro_winkler,
    name_aliases,
    name_similarity,
    names_agree,
    normalize_name,
    parse_multi_name,
)
from .provenance import provenance
from .reference import (
    compatible_states,
    depicted_year,
    is_documented_geometry_gap,
    known_geometry_gaps,
    shown_before_creation,
    state_lineage_graph,
)

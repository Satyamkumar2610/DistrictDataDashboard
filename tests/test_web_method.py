"""The web platform explains the method in plain language and quotes its thresholds; they must be the real ones.

web/src/glossary.ts holds METHOD, the numbers the "How it works" page and the glossary quote. If a threshold
changes in config/pipeline.yaml and the site still states the old one, the explanation is wrong; this fails.
"""

from __future__ import annotations

import re

from district_evolution import core

GLOSSARY = core.PROJECT_ROOT / "web" / "src" / "glossary.ts"

# METHOD key in glossary.ts -> (config section, key)
QUOTED = {
    "strongShare": ("identity", "strong"),
    "coreShare": ("identity", "core"),
    "nameRetainedShare": ("identity", "name_retained"),
    "growthMinShare": ("identity", "growth_min_h"),
    "displacementWidthKm": ("overlay", "displacement_width_km"),
    "sliverKm2": ("overlay", "sliver_abs_km2"),
}


def method_constants() -> dict[str, float]:
    block = re.search(r"export const METHOD = \{(.*?)\} as const;", GLOSSARY.read_text(encoding="utf-8"), re.S)
    assert block, "METHOD not found in web/src/glossary.ts"
    return {k: float(v) for k, v in re.findall(r"(\w+):\s*([0-9.]+)", block.group(1))}


def test_every_quoted_threshold_equals_the_config():
    quoted = method_constants()
    assert set(quoted) == set(QUOTED), f"METHOD keys changed: {sorted(quoted)}; update QUOTED here too"
    for key, (section, name) in QUOTED.items():
        assert quoted[key] == float(core.CFG[section][name]), (
            f"the site says {key}={quoted[key]} but config/pipeline.yaml {section}.{name}={core.CFG[section][name]}")


def test_the_sliver_explanation_matches_the_relative_threshold():
    """About says slivers are under 0.5 km2 or 0.01% of a large district; the second half is overlay.sliver_rel_fraction."""
    about = (core.PROJECT_ROOT / "web" / "src" / "pages" / "About.tsx").read_text(encoding="utf-8")
    assert "0.01% of a large district" in about
    assert float(core.CFG["overlay"]["sliver_rel_fraction"]) == 0.0001

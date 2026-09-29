"""Name and state normalization, similarity, and documentary aliases (renames only)."""

from __future__ import annotations

import functools
import re
import unicodedata

import pandas as pd

from .config import CFG, REFERENCE_DIR

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[.’'`,()]")
_SEP_RE = re.compile(r"[-–—/_]")


def normalize_name(value: object) -> str:
    """Matching key for a district or state name. Not a display value."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower().replace("&", " and ")
    text = _PUNCT_RE.sub("", text)
    text = _SEP_RE.sub(" ", text)
    text = re.sub(r"\bdistrict\b", " ", text)
    return _WS_RE.sub(" ", text).strip()


def display_name(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return _WS_RE.sub(" ", str(value).replace("_", " ")).strip().title()


# Census 2011 state codes, used only for the 2011 Stanford layer.
PC11_STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman and Diu", "26": "Dadra and Nagar Haveli", "27": "Maharashtra",
    "28": "Andhra Pradesh", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep",
    "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
}

# Pure spelling / rename drift of one state name (1:1). One-to-many historical
# reorganisations live in data/reference/state_lineage.csv instead.
STATE_SPELLINGS = {
    "orissa": "Odisha", "pondicherry": "Puducherry", "uttranchal": "Uttarakhand",
    "uttaranchal": "Uttarakhand", "karnatak": "Karnataka",
    "andamans and nicobars": "Andaman and Nicobar Islands",
    "andaman and nicobar": "Andaman and Nicobar Islands",
    "andaman and nicobar island": "Andaman and Nicobar Islands",
    "tamilnadu": "Tamil Nadu", "laccadive minicoy and amindiv": "Lakshadweep",
    "laccadive minicoy and amindivi islands": "Lakshadweep",
    "dadra and nagar have": "Dadra and Nagar Haveli",
    "andhra pradesh telangana": "Andhra Pradesh",
    "travancore cochin": "Travancore Cochin", "p e p s u": "Pepsu",
    "delhi": "Delhi", "nct of delhi": "Delhi",
}


def canonical_state(value: object) -> str:
    norm = normalize_name(value)
    return STATE_SPELLINGS.get(norm) or display_name(norm)


def parse_multi_name(value: object) -> list[str]:
    """Split a comma/'and'-joined list of district names (events CSV parent_district)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = re.sub(r"\band\b", ",", str(value).strip(), flags=re.IGNORECASE)
    return [p for p in (x.strip().rstrip(".").strip() for x in text.split(",")) if p]


def jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    l1, l2 = len(s1), len(s2)
    md = max(max(l1, l2) // 2 - 1, 0)
    m1, m2 = [False] * l1, [False] * l2
    matches = 0
    for i in range(l1):
        for j in range(max(0, i - md), min(i + md + 1, l2)):
            if not m2[j] and s1[i] == s2[j]:
                m1[i] = m2[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    t = k = 0
    for i in range(l1):
        if m1[i]:
            while not m2[k]:
                k += 1
            t += s1[i] != s2[k]
            k += 1
    jaro = (matches / l1 + matches / l2 + (matches - t / 2) / matches) / 3.0
    prefix = next((i for i, (a, b) in enumerate(zip(s1[:4], s2[:4])) if a != b), min(4, l1, l2))
    return jaro + prefix * p * (1.0 - jaro)


@functools.lru_cache(maxsize=1)
def name_aliases() -> pd.DataFrame:
    df = pd.read_csv(REFERENCE_DIR / "name_aliases.csv")
    df["alias_norm"] = df["alias_name"].map(normalize_name)
    df["canonical_norm"] = df["canonical_name"].map(normalize_name)
    df["state_norm"] = df["state"].map(lambda s: normalize_name(canonical_state(s)))
    return df


@functools.lru_cache(maxsize=1)
def _alias_map() -> dict[str, str]:
    a = name_aliases()
    return dict(zip(a["alias_norm"], a["canonical_norm"]))


def alias_key(name_norm: str) -> str:
    """Canonical rename/spelling key: the alias target if `name_norm` is a
    known alias, else the name itself."""
    return _alias_map().get(name_norm, name_norm)


@functools.lru_cache(maxsize=1)
def _alias_pairs() -> frozenset[tuple[str, str]]:
    a = name_aliases()
    pairs = set(zip(a["alias_norm"], a["canonical_norm"])) | set(zip(a["canonical_norm"], a["alias_norm"]))
    # aliases sharing a canonical name are aliases of each other
    for _, grp in a.groupby("canonical_norm"):
        names = list(grp["alias_norm"])
        pairs |= {(x, y) for x in names for y in names}
    return frozenset(pairs)


def _token_sort(s: str) -> str:
    return " ".join(sorted(s.split()))


def name_similarity(a_norm: str, b_norm: str) -> float:
    """Best Jaro-Winkler over raw, alias-canonical, and word-order-insensitive forms."""
    if not a_norm or not b_norm:
        return 0.0
    ka, kb = alias_key(a_norm), alias_key(b_norm)
    return max(jaro_winkler(a_norm, b_norm), jaro_winkler(ka, kb),
               jaro_winkler(_token_sort(ka), _token_sort(kb)))


# Directional / urban-rural qualifiers that mark a name DERIVED from a parent
# ("South 24 Parganas", "Purba Bardhaman", "Bangalore Urban"): a child named
# this way is a new district, not the parent continuing under its old name.
QUALIFIERS = frozenset({
    "north", "south", "east", "west", "central", "upper", "lower", "urban", "rural",
    "purba", "paschim", "pashchim", "pashchimi", "purbi", "uttar", "uttara", "dakshin",
    "dakshina", "madhya", "new", "greater",
})


def is_qualified_derivative(a_norm: str, b_norm: str) -> bool:
    """True when one name is the other plus directional qualifier(s)."""
    ta, tb = set(a_norm.split()), set(b_norm.split())
    qa, qb = ta & QUALIFIERS, tb & QUALIFIERS
    if qa == qb:
        return False
    ra, rb = " ".join(sorted(ta - QUALIFIERS)), " ".join(sorted(tb - QUALIFIERS))
    return bool(ra and rb) and (ra == rb or jaro_winkler(ra, rb) >= CFG["identity"]["name_jw"])


def names_agree(a_norm: str, b_norm: str) -> tuple[bool, float]:
    """(agree, similarity). Agreement = equal, documentary alias, or similarity >=
    config, unless one name is a qualified derivative of the other."""
    if not a_norm or not b_norm:
        return False, 0.0
    sim = name_similarity(a_norm, b_norm)
    if a_norm == b_norm or (a_norm, b_norm) in _alias_pairs():
        return True, sim
    return (sim >= CFG["identity"]["name_jw"] and not is_qualified_derivative(a_norm, b_norm)), sim

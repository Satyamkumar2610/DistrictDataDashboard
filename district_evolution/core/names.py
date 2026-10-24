"""Name and state normalization, similarity, and documentary aliases (renames only)."""

from __future__ import annotations

import functools
import re
import unicodedata
from collections.abc import Callable

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
    # the common prefix of two names of different lengths: zip stops at the shorter one on purpose
    prefix = next((i for i, (a, b) in enumerate(zip(s1[:4], s2[:4], strict=False)) if a != b), min(4, l1, l2))
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
    return dict(zip(a["alias_norm"], a["canonical_norm"], strict=True))


def alias_key(name_norm: str) -> str:
    """Canonical rename/spelling key: the alias target if `name_norm` is a
    known alias, else the name itself."""
    return _alias_map().get(name_norm, name_norm)


@functools.lru_cache(maxsize=1)
def _alias_pairs() -> frozenset[tuple[str, str]]:
    a = name_aliases()
    pairs = set(zip(a["alias_norm"], a["canonical_norm"], strict=True))
    pairs |= {(b, a_) for a_, b in pairs}
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


# ---- linkage keys (s07 parsing, s08 record linkage; never identity) ---------------------------
# Identity (s04) compares names with names_agree() and is untouched by anything below, so
# changing a linkage key can never renumber a canonical key.

# Hindi / Bengali / Kannada directional words and their English equivalents: "Paschim Medinipur"
# and "Medinipur West" are one name, "Uttara Kannada" is "North Kanara".
_QUALIFIER_EN = {
    "purba": "east", "purbi": "east", "paschim": "west", "pashchim": "west", "pashchimi": "west",
    "uttar": "north", "uttara": "north", "dakshin": "south", "dakshina": "south", "madhya": "central",
}
_EN_QUALIFIERS = frozenset(QUALIFIERS - set(_QUALIFIER_EN))
_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
_TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
          "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}


def _numerals(tokens: list[str]) -> list[str]:
    """Number words to digits: "twenty four parganas" -> "24 parganas"."""
    out, i = [], 0
    while i < len(tokens):
        t = tokens[i]
        if t in _TENS:
            n = _TENS[t]
            if i + 1 < len(tokens) and tokens[i + 1] in _UNITS:
                n += _UNITS[tokens[i + 1]]
                i += 1
            out.append(str(n))
        elif t in _TEENS:
            out.append(str(_TEENS[t]))
        else:
            out.append(t)
        i += 1
    return out


def linkage_key(name_norm: str, state_norm: str = "") -> tuple[str, str]:
    """(stem, qualifiers) of a normalised name for record linkage.

    The documentary alias is resolved first, number words become digits and directional words
    become English. Qualifiers (north, west, urban, ...) are split off: they DISTINGUISH districts
    (East Nimar is not West Nimar), so linkage requires them to be equal, while spelling
    similarity is measured on the stem alone. Measuring it on the whole name let a shared
    qualifier carry the score ("paschim medinipur" ~ "paschim bardhaman", Jaro-Winkler 0.85).
    A name that is only qualifiers keeps them as its stem, and a stem that is only the state's
    own name counts as empty ("East Sikkim" on a map is "East District" in the events, Sikkim).
    """
    if not name_norm:
        return "", ""
    tokens = _numerals([_QUALIFIER_EN.get(t, t) for t in alias_key(name_norm).split()])
    quals = sorted({t for t in tokens if t in _EN_QUALIFIERS})
    # word order is kept: Jaro-Winkler rewards a shared prefix, and sorting the words would break
    # "Kameng Frontier Division" ~ "Kameng" (compare word-order-free with sorted(stem.split()))
    stem = [t for t in tokens if t not in _EN_QUALIFIERS]
    if quals and state_norm and " ".join(stem) == state_norm:
        stem = []
    return (" ".join(stem) or " ".join(quals)), " ".join(quals)


_PARTS_OF_RE = re.compile(r"^\s*(?:the\s+)?parts?\s+of\s+", re.IGNORECASE)


def split_name_alternatives(value: object) -> list[str]:
    """'Bhimnagar/Sambhal' is ONE district under two names (Uttar Pradesh named Sambhal, Hapur and
    Shamli Bhimnagar, Panchsheel Nagar and Prabuddhanagar in 2011 and reverted in 2012), not two
    districts. Returns the alternatives, in the order written."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [p for p in (x.strip() for x in str(value).split("/")) if p]


def parse_participants(value: object, is_known: Callable[[str], bool]) -> list[tuple[str, bool]]:
    """Participants named in one events-CSV field, as (name, partial).

    Commas always separate districts. "and" separates districts only when the whole name is not a
    known district ("Dadra and Nagar Haveli", "United Khasi and Jaintia Hills" stay whole) and every
    piece is ("Malabar and South Kanara", "Moradabad and Badaun"). "Parts of A and B" names A and B,
    each contributing only part of its territory (partial=True). `is_known(name_norm)` says whether a
    name is a district on some map or a documented alias.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    out: list[tuple[str, bool]] = []
    for raw in (c.strip().rstrip(".").strip() for c in str(value).split(",")):
        if not raw:
            continue
        partial = bool(_PARTS_OF_RE.match(raw))
        chunk = _PARTS_OF_RE.sub("", raw).strip()
        pieces = [p.strip().rstrip(".").strip() for p in re.split(r"\s+(?:and|&)\s+", chunk, flags=re.IGNORECASE)]
        pieces = [p for p in pieces if p]
        whole_known = any(is_known(normalize_name(a)) for a in split_name_alternatives(chunk))
        split = (len(pieces) > 1 and not whole_known
                 and all(any(is_known(normalize_name(a)) for a in split_name_alternatives(p)) for p in pieces))
        out.extend((p, partial) for p in (pieces if split else [chunk]))
    return out

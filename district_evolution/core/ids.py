"""Deterministic identifiers."""

from __future__ import annotations

import hashlib


def stable_id(*parts: object) -> str:
    """Deterministic identifier: sha256 of a natural key. Reruns are idempotent."""
    text = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

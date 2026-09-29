"""Evidence that corroborates the maps; it never writes to geometry-derived tables."""

from .wikidata import WikidataEvidence

EVIDENCE_SOURCES = (WikidataEvidence(),)

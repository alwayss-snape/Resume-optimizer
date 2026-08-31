from typing import Dict, List, Optional

"""
Lightweight evidence index to support retrieval by source_type, section, and source_location_id.

This is an in-memory index; later work can persist to disk or a vector DB.
"""

class EvidenceIndex:
    def __init__(self):
        # index by source_location_id -> list of evidence records
        self.by_location: Dict[str, List[dict]] = {}
        # index by section name
        self.by_section: Dict[str, List[dict]] = {}

    def add(self, evidence: dict) -> None:
        loc = evidence.get("source_location_id")
        if loc:
            self.by_location.setdefault(loc, []).append(evidence)

        section = evidence.get("section")
        if section:
            self.by_section.setdefault(section, []).append(evidence)

    def find_by_location(self, source_location_id: str) -> List[dict]:
        return self.by_location.get(source_location_id, [])

    def find_by_section(self, section: str) -> List[dict]:
        return self.by_section.get(section, [])

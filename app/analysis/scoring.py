from typing import Dict, List

from app.domain.job import Requirement
from app.domain.report import Match

STATUS_WEIGHTS: Dict[str, float] = {
    "EXPLICIT": 1.00, "SUPPORTED": 0.85, "PARTIAL": 0.50,
    "UNCERTAIN": 0.00, "MISSING": 0.00,
}
CATEGORY_WEIGHTS: Dict[str, float] = {
    "skill": 0.40, "responsibility": 0.30, "qualification": 0.20,
    "preferred": 0.10, "experience": 0.20,
}

class AlignmentScorer:
    """A transparent weighted average of evidence-backed requirement coverage."""

    def calculate_score(self, matches: List[Match], requirements: List[Requirement]) -> float:
        match_map = {match.requirement_id: match for match in matches}
        weighted_score = 0.0
        total_weight = 0.0

        for requirement in requirements:
            match = match_map.get(requirement.id)
            # A positive status without cited evidence is invalid and contributes zero.
            evidence_backed = bool(match and match.evidence_ids)
            status_weight = STATUS_WEIGHTS.get(match.status, 0.0) if evidence_backed else 0.0
            category = "preferred" if requirement.priority == "preferred" else requirement.category
            weight = CATEGORY_WEIGHTS.get(category, CATEGORY_WEIGHTS["skill"])
            weighted_score += status_weight * weight
            total_weight += weight

        if not total_weight:
            return 0.0
        return round((weighted_score / total_weight) * 100.0, 1)

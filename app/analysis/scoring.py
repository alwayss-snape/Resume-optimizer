from typing import Dict, List, TypedDict

from app.domain.job import Requirement
from app.domain.report import Match


class ScoreComponents(TypedDict):
    required_coverage: float
    preferred_coverage: float
    keyword_coverage: float
    evidence_strength: float
    confidence: float


STATUS_WEIGHTS: Dict[str, float] = {
    "EXPLICIT": 1.00, "SUPPORTED": 0.85, "PARTIAL": 0.50,
    "UNCERTAIN": 0.00, "MISSING": 0.00,
}

CATEGORY_WEIGHTS: Dict[str, float] = {
    "skill": 0.40, "responsibility": 0.30, "qualification": 0.20,
    "preferred": 0.10, "experience": 0.20,
}


class AlignmentScorer:
    """A transparent weighted average of evidence-backed requirement coverage.

    Provides both a simple `calculate_score` returning a float (existing callers),
    and `calculate_components` which returns a breakdown useful for auditing.
    """

    def calculate_components(self, matches: List[Match], requirements: List[Requirement]) -> ScoreComponents:
        match_map = {match.requirement_id: match for match in matches}
        required_weighted = 0.0
        preferred_weighted = 0.0
        keyword_weighted = 0.0
        evidence_strength_total = 0.0
        required_total = preferred_total = keyword_total = 0.0

        for requirement in requirements:
            match = match_map.get(requirement.id)
            evidence_backed = bool(match and getattr(match, "evidence_ids", None))
            status_weight = STATUS_WEIGHTS.get(getattr(match, "status", "MISSING"), 0.0) if evidence_backed else 0.0

            weight = requirement.weight if requirement.weight is not None else CATEGORY_WEIGHTS.get(requirement.category, 0.2)

            if requirement.criticality == "critical" or requirement.category == "qualification":
                required_weighted += status_weight * weight
                required_total += weight
            elif requirement.criticality == "preferred":
                preferred_weighted += status_weight * weight
                preferred_total += weight
            else:
                keyword_weighted += status_weight * weight
                keyword_total += weight

            # evidence strength: average of STATUS_WEIGHTS for matched items
            if evidence_backed:
                evidence_strength_total += status_weight * weight

        def safe_div(n, d):
            return (n / d) if d else 0.0

        required_coverage = safe_div(required_weighted, required_total) * 100.0
        preferred_coverage = safe_div(preferred_weighted, preferred_total) * 100.0
        keyword_coverage = safe_div(keyword_weighted, keyword_total) * 100.0
        evidence_strength = safe_div(evidence_strength_total, (required_total + preferred_total + keyword_total)) * 100.0

        # confidence is a simple function of evidence strength and coverage
        confidence = (evidence_strength * 0.7 + (required_coverage * 0.3))

        return ScoreComponents(
            required_coverage=round(required_coverage, 1),
            preferred_coverage=round(preferred_coverage, 1),
            keyword_coverage=round(keyword_coverage, 1),
            evidence_strength=round(evidence_strength, 1),
            confidence=round(confidence, 1),
        )

    def calculate_score(self, matches: List[Match], requirements: List[Requirement]) -> float:
        comps = self.calculate_components(matches, requirements)
        # Simple aggregate: weighted sum favoring required coverage
        return round((comps["required_coverage"] * 0.6 + comps["preferred_coverage"] * 0.3 + comps["keyword_coverage"] * 0.1), 1)

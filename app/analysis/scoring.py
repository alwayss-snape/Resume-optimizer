from typing import Dict, List
from app.domain.job import Requirement
from app.domain.report import Match

STATUS_WEIGHTS: Dict[str, float] = {
    "EXPLICIT": 1.00,
    "SUPPORTED": 0.85,
    "PARTIAL": 0.50,
    "UNCERTAIN": 0.25,
    "MISSING": 0.00,
}

CATEGORY_WEIGHTS: Dict[str, float] = {
    "skill": 0.40,
    "responsibility": 0.25,
    "qualification": 0.15,
    "preferred": 0.10,
    "keyword": 0.10,
}

class AlignmentScorer:
    def calculate_score(
        self,
        matches: List[Match],
        requirements: List[Requirement],
    ) -> float:
        if not requirements or not matches:
            return 0.0

        match_map = {m.requirement_id: m for m in matches}
        
        category_scores: Dict[str, List[float]] = {
            "skill": [],
            "responsibility": [],
            "qualification": [],
            "preferred": [],
            "keyword": [],
        }

        for req in requirements:
            match = match_map.get(req.id)
            if not match:
                weight = 0.0
            else:
                weight = STATUS_WEIGHTS.get(match.status, 0.0)

            if req.priority == "preferred":
                cat_key = "preferred"
            elif req.category in category_scores:
                cat_key = req.category
            else:
                cat_key = "skill"

            category_scores[cat_key].append(weight)

        total_score = 0.0
        total_weight_applied = 0.0

        for cat, scores in category_scores.items():
            if scores:
                avg_cat = sum(scores) / len(scores)
                cat_weight = CATEGORY_WEIGHTS.get(cat, 0.10)
                total_score += avg_cat * cat_weight
                total_weight_applied += cat_weight

        if total_weight_applied == 0:
            return 0.0

        final_score = (total_score / total_weight_applied) * 100.0
        return round(final_score, 1)

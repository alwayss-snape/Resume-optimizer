from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class Match(BaseModel):
    requirement_id: str
    requirement_text: str
    status: Literal[
        "EXPLICIT",
        "SUPPORTED",
        "PARTIAL",
        "SEMANTIC_PARTIAL",
        "MISSING",
        "UNCERTAIN"
    ]
    evidence_ids: List[str] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = 1.0

class TailoringReport(BaseModel):
    alignment_score: float
    required_matches: List[Match] = Field(default_factory=list)
    preferred_matches: List[Match] = Field(default_factory=list)
    missing_requirements: List[Match] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    # Optional score breakdown (see AlignmentScorer.calculate_components).
    # Populated by analyze_only; kept optional so existing callers that don't
    # need the breakdown are unaffected.
    score_components: Optional[Dict[str, float]] = None

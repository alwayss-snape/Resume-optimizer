from typing import Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

# Jobscan's guidance for a keyword match rate; above it a resume starts to
# read as keyword-stuffed.
TARGET_BAND = (75.0, 85.0)

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

class KeywordRow(BaseModel):
    keyword: str
    kind: str  # hard | title | education | certification | soft
    required: bool = True
    weight: float
    found: bool = False
    credit: float = 0.0  # 0..1 (the title can match partially)
    where: List[str] = Field(default_factory=list)  # e.g. "skills", "summary", "Acme Corp (bullet)"
    jd_count: int = 0
    # Found only in the Skills list, nowhere in the work (P8.19): half credit.
    skills_only: bool = False


class KeywordMatchReport(BaseModel):
    rate: float  # 0..100, the headline score
    rows: List[KeywordRow] = Field(default_factory=list)
    target_band: Tuple[float, float] = TARGET_BAND
    # The JD's keywords were picked by simple rules, not the AI (P8.18).
    approximate: bool = False

    @property
    def matched(self) -> List[KeywordRow]:
        return [r for r in self.rows if r.found]

    @property
    def missing(self) -> List[KeywordRow]:
        return [r for r in self.rows if not r.found]



class TailoringReport(BaseModel):
    # Headline score: the keyword match rate (P1.2), 0-100.
    alignment_score: float
    required_matches: List[Match] = Field(default_factory=list)
    preferred_matches: List[Match] = Field(default_factory=list)
    missing_requirements: List[Match] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    # Optional score breakdown (see AlignmentScorer.calculate_components).
    # Populated by analyze_only; kept optional so existing callers that don't
    # need the breakdown are unaffected.
    score_components: Optional[Dict[str, float]] = None
    # Matched / missing keyword table behind alignment_score.
    keyword_match: Optional[KeywordMatchReport] = None
    # Job conditions that aren't keywords (P8.20): licences, shifts, lifting...
    conditions: List[Dict] = Field(default_factory=list)

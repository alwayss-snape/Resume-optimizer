from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class Requirement(BaseModel):
    id: str
    text: str
    # Normalized competency or canonical concept(s) derived from the text
    normalized_competencies: Optional[List[str]] = None
    # Source spans: list of provenance spans (e.g. {start:int, end:int, source_id:str})
    source_spans: Optional[List[dict]] = None
    category: Literal[
        "skill",
        "responsibility",
        "qualification",
        "experience",
        "domain",
        "keyword"
    ] = "skill"
    # criticality: critical/required/preferred/informational
    criticality: Literal["critical", "required", "preferred", "informational"] = "required"
    # Backwards compatible priority field used elsewhere in the codebase/tests
    priority: Literal["required", "preferred", "informational"] = "required"
    # Facets: arbitrary key->value metadata to support enrichment (e.g., level, timeframe)
    facets: Optional[dict] = None
    # Optional explicit weight to override category-based defaults for scoring
    weight: Optional[float] = None

class JobDescription(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    requirements: List[Requirement] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    raw_text: str = ""
    # JD analysis v2 (P1.1). Every string is copied verbatim from the JD.
    seniority: Optional[str] = None
    min_years: Optional[int] = None
    max_years: Optional[int] = None
    hard_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    # How often each keyword appears in the JD (counted in code).
    keyword_counts: Dict[str, int] = Field(default_factory=dict)
    # "llm" or "heuristic": which path produced the requirement list.
    analysis_source: str = "heuristic"

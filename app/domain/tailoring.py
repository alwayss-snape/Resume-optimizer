from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class TailoringAction(BaseModel):
    action: Literal[
        "KEEP",
        "REWRITE",
        "REORDER",
        "REMOVE",
        "ADD_FROM_EXISTING_EVIDENCE"
    ]
    source_id: Optional[str] = None
    target_section: str = "experience"
    evidence_ids: List[str] = Field(default_factory=list)
    rationale: str = ""
    # Planner v2 (P1.3): how relevant this bullet is to the JD (0-1), the
    # requirements it's closest to, the JD keywords a rewrite may use (terms
    # the bullet or its sub-heading already contains), and whether it's
    # among the first to drop when the resume must be shortened.
    relevance: float = 0.0
    requirement_ids: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    trim_candidate: bool = False

class ProjectChoice(BaseModel):
    """One project (a sub-heading inside a job) and whether it's kept for
    this JD (P10.13), with the reason shown on Review."""
    key: str                      # "<experience id>::<group>", what the UI sends back
    experience_id: str
    job: str                      # "Acme — Data Scientist II"
    name: str                     # the project's sub-heading
    bullet_ids: List[str] = Field(default_factory=list)
    chosen: bool = True
    reason: str = ""
    relevance: float = 0.0
    impact: float = 0.0

class TailoringPlan(BaseModel):
    actions: List[TailoringAction] = Field(default_factory=list)
    unsupported_requirements: List[str] = Field(default_factory=list)
    # experience id -> bullet ids, most relevant first within each sub-heading.
    bullet_order: Dict[str, List[str]] = Field(default_factory=dict)
    # P10.13: the projects of jobs with more than they keep, chosen or not.
    projects: List[ProjectChoice] = Field(default_factory=list)
    ranked_by_impact: bool = False  # the JD was too thin to rank projects by

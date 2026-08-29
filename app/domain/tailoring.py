from typing import List, Literal, Optional
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

class TailoringPlan(BaseModel):
    actions: List[TailoringAction] = Field(default_factory=list)
    unsupported_requirements: List[str] = Field(default_factory=list)

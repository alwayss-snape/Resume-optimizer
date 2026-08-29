from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class Requirement(BaseModel):
    id: str
    text: str
    category: Literal[
        "skill",
        "responsibility",
        "qualification",
        "experience",
        "domain",
        "keyword"
    ] = "skill"
    priority: Literal["required", "preferred", "informational"] = "required"

class JobDescription(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    requirements: List[Requirement] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    raw_text: str = ""

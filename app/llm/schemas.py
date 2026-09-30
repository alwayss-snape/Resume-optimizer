from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class LLMResponse(BaseModel):
    raw_text: str
    parsed_json: Optional[Dict[str, Any]] = None
    model_name: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    duration_seconds: Optional[float] = None


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class LLMConnectionError(LLMError):
    """Raised when Ollama server is unreachable."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM call exceeds timeout."""
    pass


class LLMInvalidJSONError(LLMError):
    """Raised when structured JSON output parsing fails after retries."""
    pass

class BulletRewriteResult(BaseModel):
    """Structured response for a single bullet rewrite/composition call."""
    rewritten: str
    rationale: str = ""
    evidence_ids: List[str] = Field(default_factory=list)


class JDRequirementLine(BaseModel):
    """One JD line the LLM judged to be a candidate requirement, by index."""
    index: int
    priority: Literal["required", "preferred"] = "required"
    category: Literal["skill", "responsibility", "qualification", "experience"] = "skill"


class JDAnalysisResult(BaseModel):
    """One structured JD analysis call (P1.1). Requirement lines are chosen
    by INDEX, and every string field must be copied verbatim from the JD:
    JDAnalyzer drops any value it can't find in the JD text, so the model
    can classify but never invent."""
    job_title: Optional[str] = None
    company: Optional[str] = None
    seniority: Optional[Literal["intern", "junior", "mid", "senior", "staff", "principal", "lead", "manager"]] = None
    min_years: Optional[int] = None
    max_years: Optional[int] = None
    requirement_lines: List[JDRequirementLine] = Field(default_factory=list)
    hard_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class RoleBulletRewrite(BaseModel):
    """One rewritten bullet from a per-role rewrite call (P1.4)."""
    bullet_id: str
    rewritten: str
    keywords_used: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)


class RoleRewriteResult(BaseModel):
    """All bullets of one role rewritten in a single call (P1.4)."""
    bullets: List[RoleBulletRewrite] = Field(default_factory=list)


class SummaryResult(BaseModel):
    """A tailored professional summary (P1.5)."""
    summary: str
    skills_used: List[str] = Field(default_factory=list)
    result_used: Optional[str] = None

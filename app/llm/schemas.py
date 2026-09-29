from typing import Any, Dict, List, Optional
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


class MissingRequirementSuggestion(BaseModel):
    """Advisory-only suggestion for a JD requirement the resume doesn't
    currently address. Never applied automatically — surfaced to the
    candidate as an example phrasing to adapt with their own real facts."""
    requirement_text: str = ""
    suggested_phrasing: str = ""
    keywords: List[str] = Field(default_factory=list)


class JDRequirementSelection(BaseModel):
    """Which job-description line indices (from a numbered list the caller
    sent) are genuine candidate requirements — skills, qualifications,
    responsibilities, or experience a candidate should be evaluated
    against — as opposed to boilerplate (company/team description,
    culture statements, benefits/perks, compensation, EEO/diversity
    statements, application instructions, generic filler). Selecting by
    INDEX rather than generating text keeps every requirement recoverable
    verbatim from the JD — see JDAnalyzer._llm_select_requirement_lines."""
    requirement_line_indices: List[int] = Field(default_factory=list)

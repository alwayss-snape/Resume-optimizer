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


class HeadingRename(BaseModel):
    original: str
    renamed: str


class HeadingRenameResult(BaseModel):
    """Plain, searchable project sub-headings for one job (P10.13)."""
    headings: List[HeadingRename] = Field(default_factory=list)


class BankJob(BaseModel):
    company: str
    title: str = ""
    start_date: str = ""
    end_date: str = ""          # "" when the notes don't say; "Present" for a current job
    line: int                   # the line that names the job


class BankProject(BaseModel):
    name: str                   # as written on its heading line
    job: int                    # index into `jobs`
    heading_line: int
    last_line: int              # the project's lines run heading_line+1 .. last_line


class BankStructure(BaseModel):
    """A project bank read as line numbers (P11.1): code keeps every line's
    words as written; the model only says what each line is."""
    jobs: List[BankJob] = Field(default_factory=list)
    projects: List[BankProject] = Field(default_factory=list)
    bullet_lines: List[int] = Field(default_factory=list)       # resume-ready statements of work
    to_verify_lines: List[int] = Field(default_factory=list)    # the notes say to check before use
    achievement_lines: List[int] = Field(default_factory=list)  # wins, awards
    skill_lines: List[int] = Field(default_factory=list)        # tools and methods lists


class SummaryResult(BaseModel):
    """A tailored professional summary (P1.5)."""
    summary: str
    skills_used: List[str] = Field(default_factory=list)
    result_used: Optional[str] = None


class JudgeRubric(BaseModel):
    """LLM-as-judge rubric for one tailored resume (P4.3)."""
    relevance: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    faithfulness: int = Field(ge=1, le=5)
    ats_readability: int = Field(ge=1, le=5)
    overall: int = Field(ge=1, le=5)
    unsupported_claims: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)


class JudgePairwise(BaseModel):
    """Which of two resume versions is better for the JD (P4.3)."""
    winner: str = Field(description='"A", "B" or "tie"')
    reason: str = ""

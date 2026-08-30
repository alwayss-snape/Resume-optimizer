from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.domain.resume import Resume

class ResumePresentation(BaseModel):
    """Display choices; content remains in the canonical Resume model."""
    template_id: str = "ats-classic"
    section_order: List[str] = Field(default_factory=lambda: [
        "summary", "experience", "projects", "skills", "education", "certifications",
    ])
    font_family: str = "Arial"
    accent_color: str = "#1F4E79"
    compact: bool = False

class ResumeSource(BaseModel):
    filename: str
    file_type: Literal["docx", "pdf", "json", "manual"]
    import_mode: Literal["preserve", "template", "manual"] = "template"

class ResumeRevision(BaseModel):
    id: str = Field(default_factory=lambda: f"rev_{uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: Literal["user", "ai", "import"] = "user"
    summary: str
    changed_paths: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)

class ResumeDocument(BaseModel):
    """Versioned source of truth for editing, tailoring, and rendering."""
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(default_factory=lambda: f"resume_{uuid4().hex[:12]}")
    resume: Resume
    presentation: ResumePresentation = Field(default_factory=ResumePresentation)
    source: Optional[ResumeSource] = None
    revisions: List[ResumeRevision] = Field(default_factory=list)

    def record_revision(
        self,
        summary: str,
        changed_paths: List[str],
        *,
        actor: Literal["user", "ai", "import"] = "user",
        evidence_ids: Optional[List[str]] = None,
    ) -> ResumeRevision:
        revision = ResumeRevision(
            actor=actor,
            summary=summary,
            changed_paths=changed_paths,
            evidence_ids=evidence_ids or [],
        )
        self.revisions.append(revision)
        return revision

    def snapshot(self) -> Dict[str, Any]:
        """Return a JSON-serializable, versioned document for storage or export."""
        return self.model_dump(mode="json")

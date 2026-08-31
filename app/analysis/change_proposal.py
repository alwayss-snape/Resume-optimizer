from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class ChangeProposal(BaseModel):
    """Richer change proposal schema for review and audit.

    Fields are intentionally explicit so the UI and validators can use them.
    """
    id: str
    target_semantic_id: Optional[str] = None
    target_source_location_id: Optional[str] = None
    original_text: str
    proposed_text: Optional[str] = None
    rationale: Optional[str] = None
    evidence_ids: Optional[List[str]] = None
    allowed_facts: Optional[List[str]] = None
    expected_score_delta: Optional[float] = None

    id: str = Field(default_factory=lambda: f"prop_{uuid4().hex[:8]}")

    model_config = {"extra": "allow"}

    def model_dump(self, *args, **kwargs):
        # Ensure backwards compatibility: include legacy keys when dumping
        data = super().model_dump(*args, **kwargs)
        # Mirror new/proposed fields to legacy names for older code
        if "proposed_text" in data and "rewritten_text" not in data:
            data["rewritten_text"] = data["proposed_text"]
        if "target_semantic_id" in data and "semantic_id" not in data:
            data["semantic_id"] = data["target_semantic_id"]
        if "target_source_location_id" in data and "source_id" not in data:
            data["source_id"] = data["target_source_location_id"]
        return data

    # Backwards-compatible accessors for older code/tests that used the
    # `RewriteProposal` shape (`semantic_id`, `source_id`, `rewritten_text`).
    @property
    def semantic_id(self) -> Optional[str]:
        # Check canonical field first, then pydantic extras and __dict__ for legacy keys
        if self.target_semantic_id:
            return self.target_semantic_id
        extras = getattr(self, "__pydantic_extra__", None)
        if extras and "semantic_id" in extras:
            return extras["semantic_id"]
        return self.__dict__.get("semantic_id")

    @property
    def source_id(self) -> Optional[str]:
        if self.target_source_location_id:
            return self.target_source_location_id
        extras = getattr(self, "__pydantic_extra__", None)
        if extras and "source_id" in extras:
            return extras["source_id"]
        return self.__dict__.get("source_id")

    @property
    def rewritten_text(self) -> str:
        if self.proposed_text:
            return self.proposed_text
        extras = getattr(self, "__pydantic_extra__", None)
        if extras and "rewritten_text" in extras:
            return extras["rewritten_text"]
        return self.__dict__.get("rewritten_text", "")

import re
from typing import List, Literal

from pydantic import BaseModel, Field

from app.analysis.rewriter import RewriteProposal
from app.domain.evidence import Evidence

class ClaimCheck(BaseModel):
    claim: str
    evidence_ids: List[str] = Field(default_factory=list)
    status: Literal["SUPPORTED", "UNSUPPORTED", "AMBIGUOUS"]
    explanation: str

class ValidationResult(BaseModel):
    approved: bool
    proposal: RewriteProposal
    claim_checks: List[ClaimCheck] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class FactualValidator:
    # Match either plain numbers with optional decimals and percent sign (e.g. 20, 3.5, 12%)
    # or currency amounts with leading $ (e.g. $5,000 or $3.5M). Use a grouped
    # alternation so word-boundary handling is consistent.
    NUMERIC_PATTERN = re.compile(r'(?:\b\d+(?:[.,]\d+)?%?\b|\$\d+(?:[.,]\d+)?\b)')
    TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9+#.-]{1,}\b")
    # Grammar and action-verb changes are allowed; factual nouns/tools are not.
    NON_FACTUAL_WORDS = {
        "a", "an", "the", "and", "or", "for", "of", "to", "in", "on", "with", "by",
        "through", "across", "using", "used", "from", "into", "that", "which", "while",
        "built", "build", "developed", "develop", "designed", "design", "led", "lead",
        "created", "create", "improved", "improve", "optimized", "optimize", "delivered",
        "enabled", "supported", "drove", "driving", "implemented", "implement",
        "architected", "managed", "helped", "contributed", "successfully",
    }

    def extract_numbers(self, text: str) -> set[str]:
        return set(self.NUMERIC_PATTERN.findall(text))

    @staticmethod
    def _canonical_term(token: str) -> str:
        token = token.lower()
        for suffix in ("ing", "ed", "es", "s"):
            if token.endswith(suffix) and len(token) > len(suffix) + 2:
                return token[:-len(suffix)]
        return token

    def _factual_terms(self, text: str) -> set[str]:
        return {
            self._canonical_term(token) for token in self.TOKEN_RE.findall(text)
            if token.lower() not in self.NON_FACTUAL_WORDS
        }

    def validate_proposal(self, proposal: RewriteProposal, evidence_list: List[Evidence]) -> ValidationResult:
        warnings: List[str] = []
        # Match evidence either by semantic id (preferred) or by raw source location id
        source_evidence = []
        for evidence in evidence_list:
            if evidence.id not in getattr(proposal, "evidence_ids", []):
                continue
            # evidence.source_id holds the canonical semantic id when available;
            # evidence.source_location_id stores the raw document block id.
            # Support both old and new proposal field names for compatibility.
            prop_sem_id = getattr(proposal, "semantic_id", None) or getattr(proposal, "target_semantic_id", None) or getattr(proposal, "source_id", None)
            if prop_sem_id and getattr(evidence, "source_id", None) == prop_sem_id:
                source_evidence.append(evidence)
                continue
            prop_loc = getattr(proposal, "source_id", None) or getattr(proposal, "target_source_location_id", None)
            if prop_loc and getattr(evidence, "source_location_id", None) == prop_loc:
                source_evidence.append(evidence)
                continue
        if not source_evidence:
            warnings.append("Rewrite rejected: no cited evidence belongs to the source bullet or location.")
        else:
            original_numbers = self.extract_numbers(getattr(proposal, "original_text", ""))
            rewritten_text = getattr(proposal, "rewritten_text", None) or getattr(proposal, "proposed_text", None) or ""
            rewritten_numbers = self.extract_numbers(rewritten_text)
            if rewritten_numbers != original_numbers:
                warnings.append("Rewrite rejected: numbers, dates, or percentages must be preserved exactly.")

            evidence_terms = set().union(*(self._factual_terms(ev.text) for ev in source_evidence))
            new_terms = self._factual_terms(rewritten_text) - evidence_terms
            if new_terms:
                warnings.append(
                    "Rewrite rejected: unsupported factual terms were introduced: "
                    + ", ".join(sorted(new_terms))
                )

        status: Literal["SUPPORTED", "UNSUPPORTED", "AMBIGUOUS"] = "SUPPORTED" if not warnings else "UNSUPPORTED"
        check = ClaimCheck(
            claim=rewritten_text, evidence_ids=getattr(proposal, "evidence_ids", []), status=status,
            explanation="All claims are traceable to the cited source bullet." if not warnings else " ".join(warnings),
        )
        return ValidationResult(
            approved=not warnings, proposal=proposal, claim_checks=[check], warnings=warnings,
        )

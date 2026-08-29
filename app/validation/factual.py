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
    NUMERIC_PATTERN = re.compile(r"\\b\\d+(?:[\\.,]\\d+)?%?\\b|\\b\\$\\d+(?:[\\.,]\\d+)?\\b")
    TOKEN_RE = re.compile(r"\\b[A-Za-z][A-Za-z0-9+#.-]{1,}\\b")
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

    def _factual_terms(self, text: str) -> set[str]:
        return {
            token.lower() for token in self.TOKEN_RE.findall(text)
            if token.lower() not in self.NON_FACTUAL_WORDS
        }

    def validate_proposal(self, proposal: RewriteProposal, evidence_list: List[Evidence]) -> ValidationResult:
        warnings: List[str] = []
        source_evidence = [
            evidence for evidence in evidence_list
            if evidence.id in proposal.evidence_ids and evidence.source_id == proposal.source_id
        ]
        if not source_evidence:
            warnings.append("Rewrite rejected: no cited evidence belongs to the source bullet.")
        else:
            original_numbers = self.extract_numbers(proposal.original_text)
            rewritten_numbers = self.extract_numbers(proposal.rewritten_text)
            if rewritten_numbers != original_numbers:
                warnings.append("Rewrite rejected: numbers, dates, or percentages must be preserved exactly.")

            evidence_terms = set().union(*(self._factual_terms(ev.text) for ev in source_evidence))
            new_terms = self._factual_terms(proposal.rewritten_text) - evidence_terms
            if new_terms:
                warnings.append(
                    "Rewrite rejected: unsupported factual terms were introduced: "
                    + ", ".join(sorted(new_terms))
                )

        status: Literal["SUPPORTED", "UNSUPPORTED", "AMBIGUOUS"] = "SUPPORTED" if not warnings else "UNSUPPORTED"
        check = ClaimCheck(
            claim=proposal.rewritten_text, evidence_ids=proposal.evidence_ids, status=status,
            explanation="All claims are traceable to the cited source bullet." if not warnings else " ".join(warnings),
        )
        return ValidationResult(
            approved=not warnings, proposal=proposal, claim_checks=[check], warnings=warnings,
        )

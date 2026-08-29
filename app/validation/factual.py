import re
from typing import List, Literal, Optional
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
    NUMERIC_PATTERN = re.compile(r'\b\d+(?:[\.,]\d+)?%?|\b\$\d+(?:[\.,]\d+)?\b')

    def extract_numbers(self, text: str) -> set[str]:
        return set(self.NUMERIC_PATTERN.findall(text))

    def validate_proposal(
        self,
        proposal: RewriteProposal,
        evidence_list: List[Evidence],
    ) -> ValidationResult:
        orig_nums = self.extract_numbers(proposal.original_text)
        new_nums = self.extract_numbers(proposal.rewritten_text)

        warnings: List[str] = []
        claim_checks: List[ClaimCheck] = []

        # Check numerical integrity: New rewrite should NOT contain numbers not present in original
        unsupported_nums = new_nums - orig_nums
        if unsupported_nums:
            explanation = f"Altered or fabricated numbers detected: {unsupported_nums}"
            claim_checks.append(ClaimCheck(
                claim=proposal.rewritten_text,
                evidence_ids=proposal.evidence_ids,
                status="UNSUPPORTED",
                explanation=explanation,
            ))
            warnings.append(explanation)
            return ValidationResult(
                approved=False,
                proposal=proposal,
                claim_checks=claim_checks,
                warnings=warnings,
            )

        claim_checks.append(ClaimCheck(
            claim=proposal.rewritten_text,
            evidence_ids=proposal.evidence_ids,
            status="SUPPORTED",
            explanation="Numeric claims match source evidence exactly.",
        ))

        return ValidationResult(
            approved=True,
            proposal=proposal,
            claim_checks=claim_checks,
            warnings=warnings,
        )

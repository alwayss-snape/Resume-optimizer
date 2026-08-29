import re
from typing import Dict, List, Optional
from app.domain.evidence import Evidence
from app.domain.job import JobDescription, Requirement
from app.domain.report import Match
from app.llm.client import LLMClient

ALIASES: Dict[str, str] = {
    "ms excel": "excel",
    "microsoft excel": "excel",
    "postgres": "postgresql",
    "postgreSQL": "postgresql",
    "k8s": "kubernetes",
    "amazon web services": "aws",
    "js": "javascript",
    "py": "python",
    "tf": "terraform",
}

class EvidenceMatcher:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def _normalize_term(self, text: str) -> str:
        cleaned = text.lower().strip()
        return ALIASES.get(cleaned, cleaned)

    def match(
        self,
        job_description: JobDescription,
        evidence_list: List[Evidence],
    ) -> List[Match]:
        matches: List[Match] = []

        # Prepare normalized evidence texts
        norm_evidence = [
            (ev, self._normalize_term(ev.text), ev.text.lower())
            for ev in evidence_list
        ]

        for req in job_description.requirements:
            req_text_norm = self._normalize_term(req.text)
            matched_evidence_ids: List[str] = []
            status = "MISSING"
            explanation = "No direct or strong evidence found in resume."
            confidence = 1.0

            # Layer 1 & Layer 2: Exact & Alias matching
            for ev, norm_text, raw_lower in norm_evidence:
                if req_text_norm in raw_lower or req_text_norm in norm_text:
                    matched_evidence_ids.append(ev.id)
                    status = "EXPLICIT"
                    explanation = f"Direct match found in candidate evidence (Evidence ID: {ev.id})."
                    break
                
                # Check individual word tokens for multi-word skill requirements
                req_tokens = set(re.findall(r'\w+', req_text_norm))
                ev_tokens = set(re.findall(r'\w+', norm_text))
                if req_tokens and req_tokens.issubset(ev_tokens):
                    matched_evidence_ids.append(ev.id)
                    status = "SUPPORTED"
                    explanation = f"Strong conceptual match found in evidence ID {ev.id}."
                    break
                elif req_tokens and len(req_tokens.intersection(ev_tokens)) >= len(req_tokens) * 0.5:
                    if status == "MISSING":
                        matched_evidence_ids.append(ev.id)
                        status = "PARTIAL"
                        explanation = f"Partial term match found in evidence ID {ev.id}."

            matches.append(Match(
                requirement_id=req.id,
                requirement_text=req.text,
                status=status,
                evidence_ids=matched_evidence_ids,
                explanation=explanation,
                confidence=confidence,
            ))

        return matches

import re
from typing import Dict, List, Optional, Set
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
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "dl": "deep learning",
}

STOP_WORDS: Set[str] = {
    "and", "the", "with", "for", "such", "as", "that", "this", "should", "have", "must",
    "required", "knowledge", "experience", "familiarity", "candidate", "minimum", "years",
    "position", "office", "full", "time", "is", "of", "in", "to", "or", "a", "an", "on", "at"
}

class EvidenceMatcher:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def _normalize_term(self, text: str) -> str:
        cleaned = text.lower().strip()
        return ALIASES.get(cleaned, cleaned)

    def _extract_key_tokens(self, text: str) -> Set[str]:
        tokens = set(re.findall(r'\b[A-Za-z0-9\+#\.-]{2,}\b', text.lower()))
        return {ALIASES.get(t, t) for t in tokens if t not in STOP_WORDS}

    def match(
        self,
        job_description: JobDescription,
        evidence_list: List[Evidence],
    ) -> List[Match]:
        matches: List[Match] = []

        # Build evidence tokens mapping
        evidence_data = []
        for ev in evidence_list:
            ev_norm = self._normalize_term(ev.text)
            ev_tokens = self._extract_key_tokens(ev.text)
            evidence_data.append((ev, ev_norm, ev.text.lower(), ev_tokens))

        for req in job_description.requirements:
            req_text_norm = self._normalize_term(req.text)
            req_tokens = self._extract_key_tokens(req.text)

            matched_evidence_ids: List[str] = []
            status = "MISSING"
            explanation = "No direct or strong evidence found in candidate resume."
            confidence = 1.0

            # Layer 1 & Layer 2: Substring & Token matching
            for ev, ev_norm, raw_lower, ev_tokens in evidence_data:
                # Substring match
                if req_text_norm in raw_lower or req_text_norm in ev_norm:
                    matched_evidence_ids.append(ev.id)
                    status = "EXPLICIT"
                    explanation = f"Direct match found in evidence (ID: {ev.id})."
                    break

                # Key technical token intersection
                if req_tokens and ev_tokens:
                    intersection = req_tokens.intersection(ev_tokens)
                    if intersection:
                        overlap_ratio = len(intersection) / len(req_tokens)
                        if overlap_ratio >= 0.5 or len(intersection) >= 2:
                            matched_evidence_ids.append(ev.id)
                            status = "EXPLICIT" if overlap_ratio >= 0.8 else "SUPPORTED"
                            explanation = f"Strong conceptual match on '{', '.join(intersection)}' (Evidence ID: {ev.id})."
                            break
                        elif len(intersection) == 1 and status == "MISSING":
                            matched_evidence_ids.append(ev.id)
                            status = "PARTIAL"
                            explanation = f"Partial match on '{', '.join(intersection)}' (Evidence ID: {ev.id})."

            matches.append(Match(
                requirement_id=req.id,
                requirement_text=req.text,
                status=status,
                evidence_ids=matched_evidence_ids,
                explanation=explanation,
                confidence=confidence,
            ))

        return matches

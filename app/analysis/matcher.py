import re
from typing import Dict, List, Optional, Set

from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.report import Match
from app.llm.client import LLMClient

ALIASES: Dict[str, str] = {
    "ms excel": "excel", "microsoft excel": "excel", "postgres": "postgresql",
    "k8s": "kubernetes", "amazon web services": "aws", "js": "javascript",
    "py": "python", "tf": "terraform", "ml": "machine learning",
    "ai": "artificial intelligence", "dl": "deep learning",
}
STOP_WORDS: Set[str] = {
    "and", "the", "with", "for", "such", "as", "that", "this", "should", "have",
    "must", "required", "knowledge", "experience", "familiarity", "candidate",
    "minimum", "years", "year", "position", "office", "full", "time", "is", "of",
    "in", "to", "or", "a", "an", "on", "at", "job", "role", "about", "description",
}
LOW_SIGNAL_TOKENS: Set[str] = {"project", "projects", "team", "teams", "work", "working"}

class EvidenceMatcher:
    """Deterministic, evidence-only matcher.

    This class never uses an LLM. A positive status always includes the specific
    source evidence that caused it; broad word overlap cannot produce SUPPORT.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client  # Kept only for backwards-compatible construction.

    def _normalize_text(self, text: str) -> str:
        value = text.lower().strip()
        for source, target in ALIASES.items():
            value = re.sub(r"\\b" + re.escape(source) + r"\\b", target, value)
        return re.sub(r"\\s+", " ", value)

    def _extract_key_tokens(self, text: str) -> Set[str]:
        tokens = set(re.findall(r"\\b[A-Za-z0-9+#.-]{2,}\\b", self._normalize_text(text)))
        return {token for token in tokens if token not in STOP_WORDS}

    def _meaningful_tokens(self, text: str) -> Set[str]:
        return self._extract_key_tokens(text) - LOW_SIGNAL_TOKENS

    def match(self, job_description: JobDescription, evidence_list: List[Evidence]) -> List[Match]:
        evidence_data = [
            (ev, self._normalize_text(ev.text), self._meaningful_tokens(ev.text))
            for ev in evidence_list if ev.text.strip()
        ]
        matches: List[Match] = []

        for req in job_description.requirements:
            req_normalized = self._normalize_text(req.text)
            req_tokens = self._meaningful_tokens(req.text)
            status, evidence_ids, explanation, confidence = (
                "MISSING", [], "No resume evidence supports this requirement.", 0.0
            )

<<<<<<< HEAD
            # Requirements that contain no substantive terms must not be scored as a match.
            if not req_tokens:
                explanation = "Not scored: the extracted requirement has no substantive, comparable terms."
            else:
                best_partial = None
                for evidence, evidence_normalized, evidence_tokens in evidence_data:
                    # Exact phrase containment is the only EXPLICIT signal.
                    if len(req_normalized) >= 3 and req_normalized in evidence_normalized:
                        status, evidence_ids, confidence = "EXPLICIT", [evidence.id], 1.0
                        explanation = f"Exact requirement text appears in resume evidence {evidence.id}."
                        break

                    overlap = req_tokens & evidence_tokens
                    coverage = len(overlap) / len(req_tokens)
                    # Strong support requires every substantive term in the same evidence item.
                    if req_tokens.issubset(evidence_tokens):
                        status, evidence_ids, confidence = "SUPPORTED", [evidence.id], 0.85
                        explanation = (
                            f"All substantive requirement terms ({', '.join(sorted(req_tokens))}) "
                            f"appear together in resume evidence {evidence.id}."
                        )
                        break
                    if overlap and (best_partial is None or coverage > best_partial[0]):
                        best_partial = (coverage, evidence.id, overlap)

                # Partial is deliberately conservative: it is informational and has
                # no strength beyond a clearly-labelled partial score.
                if status == "MISSING" and best_partial and best_partial[0] >= 0.5:
                    coverage, evidence_id, overlap = best_partial
                    status, evidence_ids, confidence = "PARTIAL", [evidence_id], round(coverage, 2)
                    explanation = (
                        f"Only {len(overlap)} of {len(req_tokens)} substantive terms match "
                        f"resume evidence {evidence_id}: {', '.join(sorted(overlap))}."
                    )
=======
            # Layer 1 & Layer 2: Exact & Alias matching
            for ev, norm_text, raw_lower in norm_evidence:
                if req_text_norm in raw_lower or req_text_norm in norm_text:
                    matched_evidence_ids.append(ev.id)
                    status = "EXPLICIT"
                    explanation = f"Direct match found in candidate evidence (Evidence ID: {ev.id})."
                    break
                
                # Check individual word/tokens for multi-word skill requirements.
                # Include common symbols used in skill names like +, #, ., and -
                token_pattern = r"[A-Za-z0-9+#._-]+"
                req_tokens = set(re.findall(token_pattern, req_text_norm))
                ev_tokens = set(re.findall(token_pattern, norm_text))
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
>>>>>>> 5ab2b72 (Phase0: fix token/numeric regexes, add dependency check, update MEMORY & CHANGELOG)

            matches.append(Match(
                requirement_id=req.id, requirement_text=req.text, status=status,
                evidence_ids=evidence_ids, explanation=explanation, confidence=confidence,
            ))
        return matches

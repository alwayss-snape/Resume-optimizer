import re
from typing import Dict, List, Optional, Set

from app.analysis.terminology import flat_alias_to_canonical
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.report import Match
from app.llm.client import LLMClient

# Single source of truth: see app/analysis/terminology.py::ALIAS_MAP.
ALIASES: Dict[str, str] = flat_alias_to_canonical()
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
            # match whole-word aliases (use raw backslash escapes)
            value = re.sub(r"\b" + re.escape(source) + r"\b", target, value)
        # collapse whitespace
        return re.sub(r"\s+", " ", value)

    def _extract_key_tokens(self, text: str) -> Set[str]:
        tokens = set(re.findall(r"\b[A-Za-z0-9+#.-]{2,}\b", self._normalize_text(text)))
        return {token for token in tokens if token not in STOP_WORDS}

    def _meaningful_tokens(self, text: str) -> Set[str]:
        return self._extract_key_tokens(text) - LOW_SIGNAL_TOKENS

    def _extract_requirement_units(self, text: str):
        """Break a requirement into comparable 'units' for coverage scoring.

        A normal word becomes a single-token unit that must be matched as-is.
        A slash-separated alternative group (e.g. "AWS/GCP", "AWS/Azure/GCP")
        becomes ONE unit satisfied by ANY ONE of its alternatives — the JD is
        listing acceptable options, not requiring every one of them. Without
        this, "Experience with public cloud (AWS/GCP)" against resume
        evidence that only mentions AWS scores as if AWS alone were 50%
        coverage of a two-token requirement, which can fall below the
        PARTIAL threshold despite an exact, real skill match being present.

        Returns a list of frozensets; each frozenset is one unit's set of
        acceptable alternative tokens (usually just one element).
        """
        normalized = self._normalize_text(text)
        units: List[frozenset] = []

        slash_group_re = re.compile(r"\b[a-z0-9+#.-]+(?:/[a-z0-9+#.-]+)+\b")
        consumed_spans = []
        for m in slash_group_re.finditer(normalized):
            alternatives = {
                alt for alt in m.group(0).split("/")
                if alt and alt not in STOP_WORDS and alt not in LOW_SIGNAL_TOKENS
            }
            if alternatives:
                units.append(frozenset(alternatives))
                consumed_spans.append(m.span())

        # Blank out the consumed slash-group spans so they aren't also
        # tokenized as independent single-word units below.
        remainder_chars = list(normalized)
        for start, end in consumed_spans:
            for i in range(start, end):
                remainder_chars[i] = " "
        remainder = "".join(remainder_chars)

        remaining_tokens = set(re.findall(r"\b[a-z0-9+#.-]{2,}\b", remainder))
        remaining_tokens = {t for t in remaining_tokens if t not in STOP_WORDS} - LOW_SIGNAL_TOKENS
        for token in remaining_tokens:
            units.append(frozenset({token}))

        return units

    def match(self, job_description: JobDescription, evidence_list: List[Evidence]) -> List[Match]:
        evidence_data = [
            (ev, self._normalize_text(ev.text), self._meaningful_tokens(ev.text))
            for ev in evidence_list if ev.text.strip()
        ]
        matches: List[Match] = []

        for req in job_description.requirements:
            req_normalized = self._normalize_text(req.text)
            req_units = self._extract_requirement_units(req.text)
            status, evidence_ids, explanation, confidence = (
                "MISSING", [], "No resume evidence supports this requirement.", 0.0
            )

            # Requirements that contain no substantive terms must not be scored as a match.
            if not req_units:
                explanation = "Not scored: the extracted requirement has no substantive, comparable terms."
            else:
                best_partial = None
                for evidence, evidence_normalized, evidence_tokens in evidence_data:
                    # Exact phrase containment is the only EXPLICIT signal.
                    if len(req_normalized) >= 3 and req_normalized in evidence_normalized:
                        status, evidence_ids, confidence = "EXPLICIT", [evidence.id], 1.0
                        explanation = f"Exact requirement text appears in resume evidence {evidence.id}."
                        break

                    satisfied_units = [unit for unit in req_units if unit & evidence_tokens]
                    coverage = len(satisfied_units) / len(req_units)
                    # Strong support requires every unit satisfied by the same evidence
                    # item — for a slash-alternative unit (e.g. AWS/GCP), any one
                    # matching alternative counts as that unit being satisfied.
                    if len(satisfied_units) == len(req_units):
                        matched_terms = sorted({next(iter(u & evidence_tokens)) for u in satisfied_units})
                        status, evidence_ids, confidence = "SUPPORTED", [evidence.id], 0.85
                        explanation = (
                            f"All substantive requirement terms ({', '.join(matched_terms)}) "
                            f"appear together in resume evidence {evidence.id}."
                        )
                        break
                    if satisfied_units and (best_partial is None or coverage > best_partial[0]):
                        matched_terms = {next(iter(u & evidence_tokens)) for u in satisfied_units}
                        best_partial = (coverage, evidence.id, matched_terms)

                # Partial is deliberately conservative: it is informational and has
                # no strength beyond a clearly-labelled partial score.
                if status == "MISSING" and best_partial and best_partial[0] >= 0.5:
                    coverage, evidence_id, overlap = best_partial
                    status, evidence_ids, confidence = "PARTIAL", [evidence_id], round(coverage, 2)
                    explanation = (
                        f"Only {len(overlap)} of {len(req_units)} substantive terms match "
                        f"resume evidence {evidence_id}: {', '.join(sorted(overlap))}."
                    )

            matches.append(Match(
                requirement_id=req.id, requirement_text=req.text, status=status,
                evidence_ids=evidence_ids, explanation=explanation, confidence=confidence,
            ))
        return matches

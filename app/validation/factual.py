import re
from typing import Iterable, List, Literal, Optional, Set

from pydantic import BaseModel, Field

from app.analysis.rewriter import RewriteProposal
from app.analysis.terminology import ALIAS_MAP
from app.domain.evidence import Evidence

Verdict = Literal["PASS", "NEEDS_CONFIRM", "REJECT"]


class ClaimCheck(BaseModel):
    claim: str
    evidence_ids: List[str] = Field(default_factory=list)
    status: Literal["SUPPORTED", "UNSUPPORTED", "AMBIGUOUS"]
    explanation: str


class ValidationResult(BaseModel):
    approved: bool
    proposal: RewriteProposal
    # PASS: grounded. NEEDS_CONFIRM: kept, but uses a factual term that is in
    # the resume elsewhere, not in this bullet's source, so the user should
    # check it. REJECT: dropped (changed numbers or unevidenced facts).
    verdict: Verdict = "PASS"
    confirm_terms: List[str] = Field(default_factory=list)
    claim_checks: List[ClaimCheck] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class FactualValidator:
    """Checks that a rewrite adds no facts beyond the resume's evidence.

    What counts as a *fact* matters. Earlier versions treated every new word
    as a fact, so ordinary rewording ("cutting", "processed", "scalable")
    was rejected and almost no rewrite survived. Now:

    - Numbers must be preserved exactly (with units: 2M, 35%, 10x, 1,000+).
    - Ordinary English words (verbs, adjectives, connectors) may change freely.
    - Factual-looking terms (tools, acronyms, proper nouns, JD skills and
      scope claims like "led a team" or "mentored") must come from the
      evidence: from this bullet's own source it's a PASS; from elsewhere
      in the resume it's NEEDS_CONFIRM; from nowhere it's a REJECT.
    """

    # A number with its unit suffix, so a metric can't change unnoticed:
    # 20, 3.5, 12%, $5,000, $3.5M, 2M, 40K, 10x, 1,000+, 5+ (years).
    # The lookbehind skips digits inside identifiers (B2B, S3, v2).
    NUMERIC_PATTERN = re.compile(r"(?<![\w.])\$?\d+(?:[.,]\d+)*(?:[%+]|[kKmMbBxX](?![A-Za-z]))?")
    # Words with optional symbol suffixes or dotted/slashed parts: C++, C#, Node.js, CI/CD.
    TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[+#]+|(?:[./-][A-Za-z0-9]+)+)?")
    # Words that assert scope or seniority. They read like ordinary English
    # but are claims about the candidate, so they need evidence.
    SCOPE_CLAIMS = {
        "lead", "led", "leading", "manage", "managed", "managing", "manager", "mentor", "mentored",
        "mentoring", "team", "teams", "hire", "hired", "hiring", "founded", "founder", "owned",
        "launched", "patent", "patented", "award", "awarded", "promoted", "headed", "supervised",
        "director", "architect", "principal", "senior", "staff",
    }

    # Words that don't carry a bullet's facts, so dropping them loses nothing:
    # connectors, generic verbs and adjectives a rewrite normally changes.
    FILLER_WORDS = {
        "and", "the", "with", "for", "from", "into", "that", "this", "these", "those", "their", "them", "then",
        "than", "through", "across", "using", "used", "use", "via", "over", "under", "about", "while", "which",
        "where", "when", "also", "more", "most", "such", "including", "include", "includes", "other", "each",
        "both", "very", "well", "key", "various", "multiple", "several", "enabling", "enable", "ensuring",
        "ensure", "helping", "help", "built", "build", "developed", "develop", "designed", "design",
        "implemented", "implement", "created", "create", "delivered", "deliver", "worked", "work", "working",
        "improved", "improve", "increased", "increase", "reduced", "reduce", "reducing", "cutting", "boost",
        "boosting", "drive", "driving", "driven", "support", "supported", "supporting", "streamlined",
        "robust", "seamless", "dynamic", "effective", "efficient", "strong", "clear", "actionable",
        "end-to-end", "fully", "highly", "based", "leveraged", "leveraging", "utilized", "utilizing",
    }
    # A rewrite keeping less than this share of the original's content words
    # probably dropped information (P1.14).
    MIN_CONTENT_RETENTION = 0.5

    def dropped_facts(self, original: str, rewritten: str, vocab: Optional[Set[str]] = None):
        """(dropped factual terms, dropped content words, retention share,
        dropped list items): what of the original a rewrite no longer says."""
        vocab = vocab if vocab is not None else set(self._canon.values()) | set(self._canon)
        new_keys = self._term_keys([rewritten])
        dropped_terms: List[str] = []
        for i, token in enumerate(self.TOKEN_RE.findall(original)):
            if not self._is_factual(token, is_first=(i == 0), vocab=vocab) or token.lower() in self.SCOPE_CLAIMS:
                continue
            if not all(self._keys(p) & new_keys for p in token.split("/") if p) and token not in dropped_terms:
                dropped_terms.append(token)
        content = []
        for token in self.TOKEN_RE.findall(original):
            low = token.lower()
            if len(low) > 3 and low not in self.FILLER_WORDS and low not in {c.lower() for c in content}:
                content.append(token)
        lost = [t for t in content if not all(self._keys(p) & new_keys for p in t.split("/") if p)]
        retention = 1.0 - len(lost) / len(content) if content else 1.0
        # Short list items ("pipeline stages, win rates, and renewal
        # conversion") that vanish entirely: the details a rewrite most
        # often drops while keeping the overall word share high.
        lost_items: List[str] = []
        for chunk in re.split(r"[,;()]|\band\b|\bincluding\b|\bsuch as\b", original):
            words = [w for w in self.TOKEN_RE.findall(chunk) if len(w) > 3 and w.lower() not in self.FILLER_WORDS]
            if 1 <= len(self.TOKEN_RE.findall(chunk)) <= 4 and words and not any(self._keys(w) & new_keys for w in words):
                lost_items.append(chunk.strip())
        return dropped_terms, lost, retention, lost_items

    def __init__(self) -> None:
        # alias -> canonical and canonical -> canonical, lower-cased (k8s -> kubernetes).
        self._canon = {}
        for canonical, aliases in ALIAS_MAP.items():
            self._canon[canonical] = canonical
            for alias in aliases:
                self._canon[alias] = canonical

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def extract_numbers(self, text: str) -> set[str]:
        # Upper-case so "10x" and "10X" (or "2m" and "2M") compare equal.
        return {n.upper() for n in self.NUMERIC_PATTERN.findall(text)}

    @staticmethod
    def _stem(word: str) -> str:
        """Crude stemmer so inflections compare equal:
        cutting/cut, processed/processing/process, services/service."""
        w = word.lower()
        for suffix in ("ing", "ed", "es", "s", "ly"):
            if w.endswith(suffix) and len(w) > len(suffix) + 2:
                w = w[: -len(suffix)]
                if len(w) > 2 and w[-1] == w[-2] and w[-1] not in "lsz":
                    w = w[:-1]  # cutt -> cut, mapp -> map
                break
        if w.endswith("e") and len(w) > 4:
            w = w[:-1]  # optimize/optimiz, service/servic
        return w

    def _keys(self, word: str) -> Set[str]:
        """All forms a term can match by: stem plus canonical alias."""
        low = word.lower()
        keys = {self._stem(low), low}
        if low in self._canon:
            keys.add(self._canon[low])
        return keys

    def _term_keys(self, texts: Iterable[str]) -> Set[str]:
        keys: Set[str] = set()
        for text in texts:
            lowered = text.lower()
            for canonical, aliases in ALIAS_MAP.items():  # multi-word canonicals ("machine learning")
                if canonical in lowered or any(re.search(rf"\b{re.escape(a)}\b", lowered) for a in aliases):
                    keys.add(canonical)
            for tok in self.TOKEN_RE.findall(text):
                for part in re.split(r"[/]", tok):
                    if part:
                        keys |= self._keys(part)
        return keys

    def _is_factual(self, token: str, is_first: bool, vocab: Set[str]) -> bool:
        low = token.lower()
        if len(token) == 1 and token.islower():
            return False  # "a" (the vocab holds "a" from "A/B"); "R" and "C" stay facts
        if low in self.SCOPE_CLAIMS:
            return True
        if re.search(r"[0-9+#./]", token):
            return True  # C++, Node.js, S3, CI/CD
        if len(token) > 1 and token.isupper():
            return True  # AWS, SQL
        if any(c.isupper() for c in token[1:]) or (token[0].isupper() and not is_first):
            return True  # FastAPI, PostgreSQL, Google (not a sentence-initial capital)
        return bool(self._keys(token) & vocab)  # a known skill written in lowercase

    def _positioned_tokens(self, text: str):
        """(token, starts_a_sentence) pairs, so the capital of every
        sentence's first word isn't mistaken for a proper noun."""
        for sentence in re.split(r"(?<=[.!?;:])\s+", text):
            for i, token in enumerate(self.TOKEN_RE.findall(sentence)):
                yield token, i == 0

    # ------------------------------------------------------------------

    def _validate_skills(self, proposal) -> ValidationResult:
        """The skills section may be reordered and respelled, never extended (P1.6)."""
        from app.analysis.skills_tailor import parse_skills, unknown_skills
        added = unknown_skills(parse_skills(getattr(proposal, "original_text", "")),
                               parse_skills(getattr(proposal, "proposed_text", None) or ""))
        warnings = ["Skills rejected: not in your resume: " + ", ".join(added)] if added else []
        verdict: Verdict = "REJECT" if added else "PASS"
        check = ClaimCheck(claim=getattr(proposal, "proposed_text", "") or "", status="SUPPORTED" if not added
                           else "UNSUPPORTED", explanation=" ".join(warnings) or "Same skills, reordered.")
        return ValidationResult(approved=not added, proposal=proposal, verdict=verdict,
                                claim_checks=[check], warnings=warnings)

    def _validate_summary(self, proposal, evidence_list: List[Evidence],
                          jd_keywords: Optional[List[str]]) -> ValidationResult:
        """A summary may draw on the whole resume (P1.5): every factual term
        must appear somewhere in it, and every number must be in it or be
        one of the proposal's allowed facts (the computed years)."""
        text = getattr(proposal, "proposed_text", None) or ""
        warnings: List[str] = []
        all_text = [ev.text for ev in evidence_list] + [getattr(proposal, "original_text", "") or ""] + list(
            getattr(proposal, "allowed_facts", None) or [])
        resume_numbers = set()
        for t in all_text:
            resume_numbers |= self.extract_numbers(t)
        allowed = set()
        for fact in getattr(proposal, "allowed_facts", None) or []:
            allowed |= self.extract_numbers(fact)
        new_numbers = self.extract_numbers(text) - resume_numbers - allowed
        resume_keys = self._term_keys(all_text)
        vocab = self._term_keys(jd_keywords or []) | set(self._canon.values()) | set(self._canon)
        unsupported = []
        for token, starts_sentence in self._positioned_tokens(text):
            if not self._is_factual(token, is_first=starts_sentence, vocab=vocab):
                continue
            if not all(self._keys(p) & resume_keys for p in token.split("/") if p) and token not in unsupported:
                unsupported.append(token)
        verdict: Verdict = "PASS"
        if new_numbers:
            verdict = "REJECT"
            warnings.append("Summary rejected: numbers not found in your resume: " + ", ".join(sorted(new_numbers)))
        if unsupported:
            verdict = "REJECT"
            warnings.append("Summary rejected: terms not found anywhere in your resume: " + ", ".join(unsupported))
        check = ClaimCheck(claim=text, evidence_ids=getattr(proposal, "evidence_ids", None) or [],
                           status="SUPPORTED" if verdict == "PASS" else "UNSUPPORTED",
                           explanation=" ".join(warnings) or "Every term and number appears in the resume.")
        return ValidationResult(approved=verdict != "REJECT", proposal=proposal, verdict=verdict,
                                claim_checks=[check], warnings=warnings)

    def validate_proposal(
        self,
        proposal: RewriteProposal,
        evidence_list: List[Evidence],
        jd_keywords: Optional[List[str]] = None,
    ) -> ValidationResult:
        warnings: List[str] = []
        confirm_terms: List[str] = []
        rewritten_text = getattr(proposal, "rewritten_text", None) or getattr(proposal, "proposed_text", None) or ""
        verdict: Verdict = "PASS"

        if getattr(proposal, "kind", "bullet") == "summary":
            return self._validate_summary(proposal, evidence_list, jd_keywords)
        if getattr(proposal, "kind", "bullet") == "skills":
            return self._validate_skills(proposal)

        # The cited evidence that belongs to this bullet (by semantic id or raw location id).
        source_evidence = []
        prop_sem_id = getattr(proposal, "semantic_id", None) or getattr(proposal, "target_semantic_id", None) or getattr(proposal, "source_id", None)
        prop_loc = getattr(proposal, "source_id", None) or getattr(proposal, "target_source_location_id", None)
        for evidence in evidence_list:
            if evidence.id not in (getattr(proposal, "evidence_ids", None) or []):
                continue
            if prop_sem_id and getattr(evidence, "source_id", None) == prop_sem_id:
                source_evidence.append(evidence)
            elif prop_loc and getattr(evidence, "source_location_id", None) == prop_loc:
                source_evidence.append(evidence)

        if not source_evidence:
            verdict = "REJECT"
            warnings.append("Rewrite rejected: no cited evidence belongs to the source bullet or location.")
        else:
            original_numbers = self.extract_numbers(getattr(proposal, "original_text", ""))
            if self.extract_numbers(rewritten_text) != original_numbers:
                verdict = "REJECT"
                warnings.append("Rewrite rejected: numbers, dates, or percentages must be preserved exactly.")

            own_keys = self._term_keys(ev.text for ev in source_evidence) | self._term_keys(
                [getattr(proposal, "original_text", "")])
            resume_keys = self._term_keys(ev.text for ev in evidence_list)
            vocab = self._term_keys(jd_keywords or []) | set(self._canon.values()) | set(self._canon)

            unsupported: List[str] = []
            for i, token in enumerate(self.TOKEN_RE.findall(rewritten_text)):
                if not self._is_factual(token, is_first=(i == 0), vocab=vocab):
                    continue
                parts = [p for p in token.split("/") if p]
                if all(self._keys(p) & own_keys for p in parts):
                    continue
                if all(self._keys(p) & resume_keys for p in parts):
                    if token not in confirm_terms:
                        confirm_terms.append(token)
                elif token not in unsupported:
                    unsupported.append(token)

            # P1.14: a rewrite must not lose information either.
            dropped_terms, lost_words, retention, lost_items = self.dropped_facts(
                getattr(proposal, "original_text", ""), rewritten_text, vocab)
            drops_info = bool(dropped_terms) or retention < self.MIN_CONTENT_RETENTION or len(lost_items) >= 2
            if drops_info:
                lost_note = dropped_terms or (lost_items if len(lost_items) >= 2 else lost_words[:6])
                warnings.append(
                    "Please check: the rewrite drops " + ", ".join(f"'{t}'" for t in lost_note)
                    + " from the original bullet."
                )

            if unsupported:
                verdict = "REJECT"
                warnings.append(
                    "Rewrite rejected: introduces terms not found anywhere in your resume: " + ", ".join(unsupported)
                )
            elif confirm_terms and verdict == "PASS":
                verdict = "NEEDS_CONFIRM"
                warnings.append(
                    "Please check: uses " + ", ".join(f"'{t}'" for t in confirm_terms)
                    + ", which appears elsewhere in your resume but not in this bullet's source."
                )
            if verdict == "PASS" and drops_info:
                verdict = "NEEDS_CONFIRM"

        status: Literal["SUPPORTED", "UNSUPPORTED", "AMBIGUOUS"] = {
            "PASS": "SUPPORTED", "NEEDS_CONFIRM": "AMBIGUOUS", "REJECT": "UNSUPPORTED"}[verdict]
        check = ClaimCheck(
            claim=rewritten_text, evidence_ids=getattr(proposal, "evidence_ids", None) or [], status=status,
            explanation="All claims are traceable to the cited source bullet." if not warnings else " ".join(warnings),
        )
        return ValidationResult(
            approved=verdict != "REJECT", proposal=proposal, verdict=verdict, confirm_terms=confirm_terms,
            claim_checks=[check], warnings=warnings,
        )

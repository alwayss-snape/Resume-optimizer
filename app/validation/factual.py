import re
from typing import Iterable, List, Literal, Optional, Set, Tuple

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
        # P8.9: the same kind of claim, so the same rule (U29)
        "oversaw", "directed", "spearheaded", "orchestrated", "coached", "trained", "educated", "precepted",
    }

    # Action verbs a rewrite may choose freely: they restate the work, they
    # don't add a fact. Anything else new needs the resume to say it (P8.9).
    ACTION_VERBS = {
        "achieved", "administered", "analysed", "analyzed", "assessed", "assisted", "automated", "closed",
        "collaborated", "completed", "conducted", "configured", "consolidated", "contributed", "coordinated",
        "documented", "drafted", "established", "evaluated", "executed", "exceeded", "expanded", "facilitated",
        "generated", "handled", "identified", "installed", "integrated", "maintained", "migrated", "monitored",
        "operated", "optimised", "optimized", "organised", "organized", "partnered", "performed", "planned",
        "prepared", "presented", "processed", "produced", "provided", "ran", "repaired", "researched",
        "resolved", "reviewed", "scheduled", "secured", "served", "shipped", "simplified", "solved", "tested",
        "tracked", "troubleshot", "updated", "upgraded", "wrote", "accelerated", "grew", "cut",
        "saved", "raised", "lowered", "enhanced", "strengthened", "refined", "modernized", "standardized",
        "provide", "providing", "perform", "performing",
    }
    # Common words that carry no claim of their own.
    GENERAL_WORDS = {
        "within", "between", "among", "after", "before", "during", "every", "without", "toward", "towards",
        "upon", "along", "around", "many", "much", "same", "some", "they", "what", "will", "would", "could",
        "should", "have", "been", "being", "were", "into", "onto", "less", "least", "high", "higher", "quality",
        "results", "result", "process", "processes", "operations", "daily", "weekly", "monthly", "annual",
        "annually", "your", "only", "just", "including", "per", "first", "time", "times", "year", "years",
        "month", "months", "week", "weeks", "total", "overall", "new", "existing", "current", "currently",
        # Words every resume and JD share; they claim nothing (Stage I gate)
        "experience", "experienced", "certification", "certifications", "certified", "skills", "skilled", "role",
        "roles", "position", "setting", "settings", "environment", "environments", "background",
        "licence", "license", "licensed", "licenced", "credential", "credentials", "holds", "holding",
    }
    # Irregular past tenses, so "Troubleshoot" -> "Troubleshot" isn't a dropped word.
    IRREGULAR = {"troubleshot": "troubleshoot", "ran": "run", "led": "lead", "built": "build", "wrote": "write",
                 "taught": "teach", "drove": "drive", "grew": "grow", "made": "make", "sold": "sell", "won": "win",
                 "began": "begin", "brought": "bring", "bought": "buy", "chose": "choose", "held": "hold",
                 "kept": "keep", "met": "meet", "oversaw": "oversee", "spent": "spend", "took": "take",
                 "sought": "seek", "rebuilt": "rebuild", "rewrote": "rewrite", "undertook": "undertake",
                 "taught": "teach", "fed": "feed", "flew": "fly", "gave": "give", "went": "go", "sent": "send"}

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
    _SUPERLATIVE_RE = re.compile(
        r"\b(?:largest|biggest|first|only|record|highest|fastest|top|best|youngest|#1|sole)\b", re.IGNORECASE)

    # A rewrite keeping less than this share of the original's content words
    # probably dropped information (P1.14).
    MIN_CONTENT_RETENTION = 0.5

    def dropped_facts(self, original: str, rewritten: str, vocab: Optional[Set[str]] = None):
        """(dropped factual terms, dropped content words, retention share,
        dropped list items): what of the original a rewrite no longer says."""
        vocab = vocab if vocab is not None else set(self._canon.values()) | set(self._canon)
        new_keys = self._term_keys([rewritten])
        dropped_terms: List[str] = []
        # P8.11: a superlative is a claim of its own ("largest deal in company history").
        for word in re.findall(self._SUPERLATIVE_RE, original):
            if not re.search(rf"\b{re.escape(word)}\b", rewritten, re.IGNORECASE) and word not in dropped_terms:
                dropped_terms.append(word)
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
        # US / UK spellings compare equal (Stage I review): containerised /
        # containerized, organisation / organization, colour / color.
        w = re.sub(r"isation$", "ization", w)
        w = re.sub(r"is(e|ed|es|ing)$", r"iz\1", w) if len(w) > 5 else w
        w = re.sub(r"our$", "or", w) if len(w) > 5 else w
        w = re.sub(r"lling$", "ling", w)
        w = re.sub(r"lled$", "led", w)
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
        if low in self.IRREGULAR:
            keys |= {self.IRREGULAR[low], self._stem(self.IRREGULAR[low])}
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
                        for piece in part.split("-"):  # "post-operative" also gives post, operative
                            if piece and piece != part:
                                keys |= self._keys(piece)
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

    def _validate_project(self, proposal, evidence_list: List[Evidence], jd_keywords, jd_text) -> ValidationResult:
        """A project written whole (P11.5): every new bullet is checked like a
        rewrite, against the project's own material (its bullets, the owner's
        notes and answers) instead of one source bullet; a figure the project
        had and no new bullet keeps is worth a look."""
        cited = set(getattr(proposal, "evidence_ids", None) or [])
        material = [e.text for e in evidence_list if e.id in cited]
        original = getattr(proposal, "original_text", "") or ""
        sid = f"__project__{getattr(proposal, 'id', '')}"
        synthetic = [Evidence(id=f"{sid}_{i}", source_type="experience", source_id=sid, text=t)
                     for i, t in enumerate(material or [original])]
        whole = "\n".join([original, *material])
        lines = [l.strip() for l in (getattr(proposal, "proposed_text", None) or "").splitlines() if l.strip()]
        rank = {"PASS": 0, "NEEDS_CONFIRM": 1, "REJECT": 2}
        verdict: Verdict = "PASS" if lines else "REJECT"
        warnings: List[str] = [] if lines else ["Rewrite rejected: no bullets."]
        confirm: List[str] = []
        for n, line in enumerate(lines, start=1):
            one = RewriteProposal(target_semantic_id=sid, target_source_location_id=sid, original_text=whole,
                                  proposed_text=line, evidence_ids=[e.id for e in synthetic])
            one.numbers_subset = True
            result = self.validate_proposal(one, list(evidence_list) + synthetic, jd_keywords=jd_keywords, jd_text=jd_text)
            if rank[result.verdict] > rank[verdict]:
                verdict = result.verdict
            warnings += [f"Bullet {n}: {w}" for w in result.warnings]
            confirm += [t for t in result.confirm_terms if t not in confirm]
        kept = self.extract_numbers("\n".join(lines))
        lost = sorted(self.extract_numbers(original) - kept)
        if lost and verdict != "REJECT":
            warnings.append("Please check: leaves out " + ", ".join(lost) + " from this project.")
            verdict = "NEEDS_CONFIRM" if verdict == "PASS" else verdict
        return ValidationResult(approved=verdict != "REJECT", proposal=proposal, verdict=verdict,
                                confirm_terms=confirm, warnings=warnings)

    def _validate_heading(self, proposal, evidence_list: List[Evidence]) -> ValidationResult:
        """A project heading (P10.13) may only reword what the old heading and
        the project's own bullets say."""
        from app.analysis.project_select import heading_problem
        cited = set(getattr(proposal, "evidence_ids", None) or [])
        sources = [getattr(proposal, "original_text", "") or ""] + [e.text for e in evidence_list if e.id in cited]
        problem = heading_problem(getattr(proposal, "proposed_text", None) or "", sources)
        warnings = [f"Heading rejected: {problem}"] if problem else []
        verdict: Verdict = "REJECT" if problem else "PASS"
        return ValidationResult(approved=not problem, proposal=proposal, verdict=verdict, warnings=warnings)

    def _validate_skills(self, proposal, evidence_list: Optional[List[Evidence]] = None) -> ValidationResult:
        """The skills section may be reordered and respelled, and gain what the
        candidate's own material names (P11.7: never beyond evidence; was
        never extended, P1.6)."""
        from app.analysis.skills_tailor import _in_material, _key, parse_skills, unknown_skills
        added = unknown_skills(parse_skills(getattr(proposal, "original_text", "")),
                               parse_skills(getattr(proposal, "proposed_text", None) or ""))
        keys = " " + " ".join(_key(e.text) for e in evidence_list or []) + " "
        added = [a for a in added if not _in_material(a, keys)]
        # A category's name is a claim too (P11.7): only plain category words or the material's own.
        from app.analysis.skills_tailor import category_name
        old_names = {c.lower() for c in parse_skills(getattr(proposal, "original_text", ""))}
        added += [f"{c} (category)" for c in parse_skills(getattr(proposal, "proposed_text", None) or "")
                  if c.lower() not in old_names and category_name(c, keys + " " + _key(getattr(proposal, "original_text", "")) + " ") != c]
        warnings = ["Skills rejected: not in your resume: " + ", ".join(added)] if added else []
        verdict: Verdict = "REJECT" if added else "PASS"
        check = ClaimCheck(claim=getattr(proposal, "proposed_text", "") or "", status="SUPPORTED" if not added
                           else "UNSUPPORTED", explanation=" ".join(warnings) or "Same skills, reordered.")
        return ValidationResult(approved=not added, proposal=proposal, verdict=verdict,
                                claim_checks=[check], warnings=warnings)

    def _validate_achievement(self, proposal, evidence_list: List[Evidence]) -> ValidationResult:
        """P11.15: an achievement may only gain "(where, when)", and every word
        and number of it must be in the resume or notes (a job's company, a
        year a project's own lines give)."""
        from app.analysis.achievement_context import added_context
        original = getattr(proposal, "original_text", "") or ""
        text = getattr(proposal, "proposed_text", None) or ""
        context = added_context(original, text)
        sources = [ev.text for ev in evidence_list] + [
            " ".join(filter(None, (ev.source_id, getattr(ev, "source_location_id", None)))) for ev in evidence_list]
        sources += list(getattr(proposal, "allowed_facts", None) or [])
        warnings: List[str] = []
        if context is None:
            warnings.append("Achievement rejected: only where and when may be added; reword it yourself to change more.")
        else:
            known = self._term_keys(sources)
            numbers = set()
            for t in sources:
                numbers |= self.extract_numbers(t)
            new_numbers = self.extract_numbers(context) - numbers
            unknown = [w for w in self.TOKEN_RE.findall(context) if not self._keys(w) & known]
            if new_numbers or unknown:
                warnings.append("Achievement rejected: not found in your resume or notes: "
                                + ", ".join([*sorted(new_numbers), *unknown]))
        ok = not warnings
        check = ClaimCheck(claim=text, status="SUPPORTED" if ok else "UNSUPPORTED",
                           explanation=" ".join(warnings) or "Where and when come from your resume and notes.")
        return ValidationResult(approved=ok, proposal=proposal, verdict="PASS" if ok else "REJECT",
                                claim_checks=[check], warnings=warnings)

    def _validate_summary(self, proposal, evidence_list: List[Evidence],
                          jd_keywords: Optional[List[str]], jd_text: Optional[str] = None) -> ValidationResult:
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
        # P8.10: a repeated phrase ("B2B SaaS sales in B2B SaaS") reads as filler.
        words = [w.lower() for w in self.TOKEN_RE.findall(text)]
        stop = self.FILLER_WORDS | {"of", "in", "to", "on", "at", "as", "by", "an", "a", "or", "years", "year"}
        pairs = [f"{a} {b}" for a, b in zip(words, words[1:])
                 if a not in stop and b not in stop and len(a) > 2 and len(b) > 2]
        repeated = sorted({p for p in pairs if pairs.count(p) > 1})
        if repeated:
            verdict = "REJECT"
            warnings.append("Summary rejected: repeats " + ", ".join(f"'{p}'" for p in repeated))
        # P8.9: plain words that only the job description uses are claims too.
        borrowed, _ = self._new_words(text, resume_keys, resume_keys, self._term_keys([jd_text]) if jd_text else set())
        if len(borrowed) == 1 and verdict == "PASS":
            verdict = "NEEDS_CONFIRM"
            warnings.append(f"Please check: '{borrowed[0]}' comes from the job description, not your resume.")
        elif borrowed:
            verdict = "REJECT"
            warnings.append("Summary rejected: borrows the job description's wording, which your resume doesn't "
                            "support: " + ", ".join(f"'{t}'" for t in borrowed))
        # P11.13: "builds optimization models" from "hyperparameter optimization"
        # passes a word check; the kind of work claimed must be a phrase the
        # resume itself uses.
        for phrase, seen in self._work_claims_unsupported(text, all_text):
            if verdict == "PASS":
                verdict = "NEEDS_CONFIRM"
            hint = f" (your resume says '{seen}')" if seen else ""
            warnings.append(f"Please check: the summary says '{phrase}', which isn't a phrase your resume uses{hint}.")
        check = ClaimCheck(claim=text, evidence_ids=getattr(proposal, "evidence_ids", None) or [],
                           status="SUPPORTED" if verdict == "PASS" else "UNSUPPORTED",
                           explanation=" ".join(warnings) or "Every term and number appears in the resume.")
        return ValidationResult(approved=verdict != "REJECT", proposal=proposal, verdict=verdict,
                                claim_checks=[check], warnings=warnings)

    # P11.13: a work verb in a summary, then the kind of work it claims.
    WORK_VERBS = ("build", "builds", "building", "develop", "develops", "developing", "design", "designs",
                  "designing", "deliver", "delivers", "delivering", "create", "creates", "creating", "deploy",
                  "deploys", "deploying", "ship", "ships", "shipping", "architect", "architects", "architecting")
    # These start a claim only before "in" / "with" / "on" ("experienced in X",
    # not "Experienced backend engineer").
    LEAD_VERBS = ("specializing", "specialising", "specializes", "specialises", "focused", "focusing",
                  "expertise", "experience", "experienced", "skilled")
    CLAIM_STOPS = {"and", "or", "for", "to", "with", "that", "across", "using", "at", "in", "on", "by", "from",
                   "which", "while", "into", "through", "via", "of", "as", "who", "where", "when", "than"}
    CLAIM_LEAD = {"in", "with", "on", "a", "an", "the"}
    ARTICLES = {"a", "an", "the"}
    REVERSED_BY = {"in", "for", "of", "with", "on"}  # "dashboards in Power BI" shows "Power BI dashboards"

    def _claim_words(self, text: str) -> List[List[str]]:
        """Content words of each work claim, in order: "builds optimization
        models for pricing" -> ["optimization", "models"]."""
        claims: List[List[str]] = []
        current: Optional[List[str]] = None
        pending = False  # a lead verb waiting for its "in" / "with" / "on"
        last_end = 0
        for m in self.TOKEN_RE.finditer(text):
            low = m.group(0).lower()
            if re.search(r"[,.;:()!?]", text[last_end:m.start()]):
                if current:
                    claims.append(current)
                current, pending = None, False
            last_end = m.end()
            if pending:
                pending = False
                current = [] if low in ("in", "with", "on") else None
                continue
            if low in self.WORK_VERBS or low in self.LEAD_VERBS:
                if current:
                    claims.append(current)
                current, pending = (None, True) if low in self.LEAD_VERBS else ([], False)
                continue
            if current is None:
                continue
            if not current and low in self.CLAIM_LEAD:
                continue
            if low in self.CLAIM_STOPS:
                claims.append(current)
                current = None
                continue
            if low not in self.FILLER_WORDS and low not in self.GENERAL_WORDS:
                current.extend(p for p in m.group(0).split("-") if p)
        if current:
            claims.append(current)
        return [c for c in claims if c]

    def _pair_keys(self, word: str) -> Set[str]:
        """A word's keys plus, for an alias of a longer term ("ML"), the keys of
        that term's last word, so "ML models" and "machine learning models" pair."""
        keys = self._keys(word)
        canon = self._canon.get(word.lower())
        if canon and " " in canon:
            keys |= self._keys(canon.split()[-1])
        return keys

    def _work_claims_unsupported(self, text: str, sources: List[str]) -> List[Tuple[str, Optional[str]]]:
        """Claims of two or more words whose last two (the kind of work) are
        not next to each other in any one line of the resume (or written the
        other way round, "dashboards in Power BI"), with a pair the resume
        does use for a hint."""
        lines = []
        for src in sources:
            tokens = [t for t in self._content_tokens(src or "") if t.lower() not in self.ARTICLES]
            lines.append([(t, self._pair_keys(t)) for t in tokens])
        out: List[Tuple[str, Optional[str]]] = []
        for words in self._claim_words(text):
            if len(words) < 2:
                continue
            a, b = self._pair_keys(words[-2]), self._pair_keys(words[-1])
            found, hint = False, None
            for tokens in lines:
                for i, (x, kx) in enumerate(tokens[:-1]):
                    y, ky = tokens[i + 1]
                    if kx & a and ky & b:
                        found = True
                    elif kx & b and y.lower() in self.REVERSED_BY and any(k & a for _, k in tokens[i + 2:i + 5]):
                        found = True
                    elif hint is None and ky & a and x.lower() not in self.FILLER_WORDS \
                            and x.lower() not in self.GENERAL_WORDS:
                        hint = f"{x} {y}"
                    if found:
                        break
                if found:
                    break
            if not found:
                out.append((" ".join(words[-2:]), hint))
        return out

    @staticmethod
    def _owner_prefix(semantic_id: Optional[str]) -> Optional[str]:
        """'exp_001_b03' -> 'exp_001_': the job (or project) a bullet belongs to."""
        m = re.match(r"^((?:exp|proj)_\d+_)", semantic_id or "")
        return m.group(1) if m else None

    def _content_tokens(self, text: str):
        """Plain words of a text in order, hyphenated words split into parts
        ("critically-ill" -> critically, ill)."""
        for token in self.TOKEN_RE.findall(text):
            for part in token.split("-"):
                if part:
                    yield part

    def _is_plain(self, low: str) -> bool:
        return len(low) > 3 and low.isalpha() and not (
            low in self.FILLER_WORDS or low in self.ACTION_VERBS or low in self.GENERAL_WORDS
            or self._stem(low) in {self._stem(v) for v in self.ACTION_VERBS})

    def _new_words(self, text: str, own_keys: Set[str], resume_keys: Set[str], jd_keys: Set[str]):
        """Plain words a rewrite adds (P8.9): (borrowed from the JD only,
        not in the resume at all). Factual terms are checked separately."""
        borrowed: List[str] = []
        unknown: List[str] = []
        for token in self._content_tokens(text):
            low = token.lower()
            if not self._is_plain(low):
                continue
            keys = self._keys(low)
            if keys & own_keys or keys & resume_keys:
                continue
            if keys & jd_keys:
                if token not in borrowed:
                    borrowed.append(token)
            elif token not in unknown:
                unknown.append(token)
        return borrowed, unknown

    def _words_from_elsewhere(self, text: str, near_keys: Set[str], resume_keys: Set[str]) -> List[List[str]]:
        """Runs of consecutive plain words that the resume uses only under
        another job or section (Stage I review: "titrating cardiac drips"
        moved from one hospital job to another passed as ordinary words)."""
        runs: List[List[str]] = []
        current: List[str] = []
        for token in self._content_tokens(text):
            low = token.lower()
            if not self._is_plain(low):
                continue  # filler doesn't break a run ("drips and monitoring")
            keys = self._keys(low)
            if keys & resume_keys and not keys & near_keys:
                current.append(token)
            else:
                if current:
                    runs.append(current)
                current = []
        if current:
            runs.append(current)
        return runs

    def validate_proposal(
        self,
        proposal: RewriteProposal,
        evidence_list: List[Evidence],
        jd_keywords: Optional[List[str]] = None,
        jd_text: Optional[str] = None,
    ) -> ValidationResult:
        warnings: List[str] = []
        confirm_terms: List[str] = []
        rewritten_text = getattr(proposal, "rewritten_text", None) or getattr(proposal, "proposed_text", None) or ""
        verdict: Verdict = "PASS"

        if getattr(proposal, "kind", "bullet") == "summary":
            return self._validate_summary(proposal, evidence_list, jd_keywords, jd_text)
        if getattr(proposal, "kind", "bullet") == "skills":
            return self._validate_skills(proposal, evidence_list)
        if getattr(proposal, "kind", "bullet") == "achievement":
            return self._validate_achievement(proposal, evidence_list)
        if getattr(proposal, "kind", "bullet") == "heading":
            return self._validate_heading(proposal, evidence_list)
        if getattr(proposal, "kind", "bullet") == "project":
            return self._validate_project(proposal, evidence_list, jd_keywords, jd_text)

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
            subset = getattr(proposal, "numbers_subset", False)  # P11.5: one bullet of a project uses some of its figures
            new_numbers = self.extract_numbers(rewritten_text)
            if (new_numbers - original_numbers) if subset else (new_numbers != original_numbers):
                verdict = "REJECT"
                warnings.append("Rewrite rejected: numbers, dates, or percentages must be preserved exactly.")

            own_keys = self._term_keys(ev.text for ev in source_evidence) | self._term_keys(
                [getattr(proposal, "original_text", "")])
            resume_keys = self._term_keys(ev.text for ev in evidence_list)
            vocab = self._term_keys(jd_keywords or []) | set(self._canon.values()) | set(self._canon)
            # P8.9: a fact must come from this job, its sub-headings, the
            # skills list or the summary; one found only under another job
            # or section (a student rotation, another employer) is not this
            # job's to claim (U2).
            prefix = self._owner_prefix(prop_sem_id)
            near_keys = self._term_keys(
                ev.text for ev in evidence_list
                if (prefix and (ev.source_id or "").startswith(prefix))
                or ev.source_type in ("skill", "summary", "certification", "education"))

            unsupported: List[str] = []
            elsewhere: List[str] = []
            for i, token in enumerate(self.TOKEN_RE.findall(rewritten_text)):
                if not self._is_factual(token, is_first=(i == 0), vocab=vocab):
                    continue
                parts = [p for p in token.split("/") if p]
                if all(self._keys(p) & own_keys for p in parts):
                    continue
                scope = token.lower() in self.SCOPE_CLAIMS
                if all(self._keys(p) & (resume_keys if scope or not prefix else near_keys) for p in parts):
                    if token not in confirm_terms:
                        confirm_terms.append(token)
                elif all(self._keys(p) & resume_keys for p in parts):
                    if token not in elsewhere:
                        elsewhere.append(token)
                elif token not in unsupported:
                    unsupported.append(token)

            jd_keys = self._term_keys([jd_text]) if jd_text else set()
            borrowed, unknown_words = self._new_words(rewritten_text, own_keys, resume_keys, jd_keys)
            moved = self._words_from_elsewhere(rewritten_text, own_keys | near_keys, resume_keys) if prefix else []

            # P1.14: a rewrite must not lose information either.
            dropped_terms, lost_words, retention, lost_items = self.dropped_facts(
                getattr(proposal, "original_text", ""), rewritten_text, vocab)
            drops_info = bool(dropped_terms) or retention < self.MIN_CONTENT_RETENTION or len(lost_items) >= 2
            if subset:  # judged for the project as a whole (_validate_project)
                drops_info = False
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
            if elsewhere:
                verdict = "REJECT"
                warnings.append(
                    "Rewrite rejected: uses " + ", ".join(f"'{t}'" for t in elsewhere)
                    + " from another part of your resume, not this job."
                )
            if any(len(run) >= 2 for run in moved):
                verdict = "REJECT"
                warnings.append("Rewrite rejected: describes work your resume lists under another job: "
                                + "; ".join(f"'{' '.join(run)}'" for run in moved if len(run) >= 2))
            elif moved and verdict == "PASS":
                verdict = "NEEDS_CONFIRM"
                warnings.append("Please check: uses " + ", ".join(f"'{run[0]}'" for run in moved)
                                + " from another part of your resume, not this job.")
            # One JD-only word is worth a look; two or more are the JD's claim (Stage I review).
            if len(borrowed) >= 2:
                verdict = "REJECT"
                warnings.append(
                    "Rewrite rejected: borrows the job description's wording, which your resume doesn't support: "
                    + ", ".join(f"'{t}'" for t in borrowed)
                )
            elif borrowed and verdict == "PASS":
                verdict = "NEEDS_CONFIRM"
                warnings.append(f"Please check: '{borrowed[0]}' comes from the job description, not your resume.")
            if verdict == "PASS" and len(unknown_words) >= 2:
                verdict = "NEEDS_CONFIRM"
                warnings.append(
                    "Please check: adds wording your resume doesn't use: " + ", ".join(f"'{t}'" for t in unknown_words)
                )
            if confirm_terms and verdict == "PASS":
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

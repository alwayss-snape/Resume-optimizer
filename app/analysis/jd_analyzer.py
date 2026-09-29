import re
from typing import List, Optional, Set

from app.domain.job import JobDescription, Requirement
from app.llm.client import LLMClient
from app.llm.schemas import JDRequirementSelection

class JDAnalyzer:
    """Extract only text that is visibly present in the supplied job description."""

    STOP_WORDS = {
        "and", "the", "with", "for", "such", "as", "that", "this", "should", "have",
        "must", "required", "knowledge", "experience", "familiarity", "job", "role",
        "about", "description", "responsibilities", "requirements", "qualifications",
    }
    HEADING_RE = re.compile(
        r"^(about( the)? job|about us|what we offer|benefits|equal opportunity|"
        r"nice to have|who you are|what you.ll do|"
        r"(minimum|required|basic|desired|preferred|additional|other|key|core|"
        r"technical|essential|primary|general)?\s*"
        r"(responsibilit(y|ies)|requirements?|qualifications?|skills)"
        r")[:\s]*$",
        re.IGNORECASE,
    )
    REQUIREMENT_SIGNALS = (
        "must", "required", "requirement", "qualified", "qualification", "proficien",
        "experience", "years", "degree", "bachelor", "master", "phd", "responsible",
        "responsibilities", "develop", "design", "build", "manage", "lead", "create",
        "implement", "maintain", "analyze", "collaborate", "knowledge of", "ability to",
    )
    PREFERRED_SIGNALS = ("preferred", "nice to have", "optional", "bonus", "plus")

    # Marks a bulleted line, in any of the glyph variants seen in real JDs.
    BULLET_LINE_RE = re.compile(r"^[-•*▪●◦‣▸–—]\s+")

    def __init__(self, llm_client: Optional[LLMClient] = None):
        # Used ONLY to pick which lines are genuine requirements vs
        # boilerplate (see _llm_select_requirement_lines) — never to
        # generate or paraphrase requirement text. Every requirement kept
        # is still one of the exact lines pulled straight from the JD, so
        # scoring stays recoverable verbatim from the source text. When
        # unavailable, analyze() falls back fully to the deterministic
        # REQUIREMENT_SIGNALS heuristic below.
        self.llm_client = llm_client

    def extract_keywords_from_text(self, text: str) -> List[str]:
        words = re.findall(r"\\b[A-Za-z0-9+#.-]{2,}\\b", text)
        return list(dict.fromkeys(
            word.strip(".,()") for word in words
            if word.strip(".,()").lower() not in self.STOP_WORDS
        ))

    def _category(self, line: str) -> str:
        lowered = line.lower()
        if any(k in lowered for k in ("degree", "education", "bachelor", "master", "phd")):
            return "qualification"
        if any(k in lowered for k in (
            "responsible", "develop", "design", "build", "manage", "lead", "implement",
            "maintain", "analyze", "collaborate", "create",
        )):
            return "responsibility"
        return "skill"

    def _is_requirement(self, line: str, was_bullet: bool, in_requirement_section: bool) -> bool:
        lowered = line.lower()
        if self.HEADING_RE.match(line) or len(line) < 4:
            return False
        # Bullets under a requirements-like heading are explicit source items.
        return was_bullet or in_requirement_section or any(
            signal in lowered for signal in self.REQUIREMENT_SIGNALS
        )

    def _segment_line(self, line: str) -> List[str]:
        """Conservatively split a requirement line into atomic requirement phrases.

        Strategy:
        - Split on semicolons first.
        - Split on ' and ' when the clause contains an action verb signal to avoid
          splitting simple enumerations of nouns.
        """
        parts = [p.strip() for p in re.split(r";", line) if p.strip()]
        atomic: List[str] = []
        verbs = [v for v in self.REQUIREMENT_SIGNALS if v.isalpha()]
        for p in parts:
            lowered = p.lower()
            if " and " in lowered and any(v in lowered for v in verbs):
                subparts = [s.strip() for s in re.split(r"\band\b", p) if s.strip()]
                atomic.extend(subparts)
            else:
                atomic.append(p)
        return atomic

    def _reflow_lines(self, jd_text: str) -> List[str]:
        """Undo hard line-wrapping from pasted JDs (job boards/PDFs often wrap
        a single sentence or bullet across multiple lines at a fixed width).
        Left as separate lines, a wrapped requirement shreds into
        unrelated-looking fragments that get scored independently. A
        continuation line is merged into the previous line when: it isn't
        itself a new bullet or a section heading, the previous line doesn't
        already end at a sentence/clause boundary, and it starts with a
        lowercase letter — the strongest cheap signal that it continues the
        prior clause rather than starting a new label/heading/sentence
        (which almost always starts uppercase, e.g. "Company: Acme Inc.")."""
        raw_lines = [l.strip() for l in jd_text.splitlines()]
        reflowed: List[str] = []
        for line in raw_lines:
            if not line:
                reflowed.append("")  # preserve paragraph breaks
                continue
            is_bullet = bool(self.BULLET_LINE_RE.match(line))
            is_heading_like = bool(self.HEADING_RE.match(line))
            starts_lowercase = line[0].islower()
            prev = reflowed[-1] if reflowed else ""
            prev_ends_clause = (not prev) or bool(re.search(r"[.:;!?]$", prev))
            if (
                reflowed
                and prev
                and not is_bullet
                and not is_heading_like
                and not prev_ends_clause
                and starts_lowercase
            ):
                reflowed[-1] = f"{prev} {line}".strip()
            else:
                reflowed.append(line)
        return [l for l in reflowed if l]

    def _llm_select_requirement_lines(
        self, lines: List[str], candidate_indices: List[int]
    ) -> Optional[Set[int]]:
        """Ask the LLM which of the given candidate line indices are genuine
        candidate requirements, as opposed to boilerplate. Returns None
        (caller falls back to the deterministic heuristic) when no LLM is
        configured, it's unreachable, the call fails, or the response looks
        degenerate. The LLM selects by INDEX only — it never generates or
        rewrites text — so every requirement kept is guaranteed to be one
        of the exact lines pulled from the JD."""
        if not candidate_indices:
            return None
        if not self.llm_client or not self.llm_client.is_available():
            return None

        numbered = "\n".join(f"{i}: {lines[i]}" for i in candidate_indices)
        system_prompt = (
            "You identify which lines of a job description are genuine "
            "candidate requirements: skills, qualifications, responsibilities, "
            "or experience a candidate should be evaluated against.\n\n"
            "Exclude boilerplate: company/team descriptions, culture or mission "
            "statements, benefits/perks/compensation, EEO/diversity statements, "
            "application instructions, and generic filler sentences.\n\n"
            "Return ONLY the 0-based line indices of genuine requirement lines, "
            "exactly as given in the numbered list below. Never rewrite, "
            "paraphrase, summarize, or invent text — select indices only."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Numbered lines:\n{numbered}"},
        ]
        try:
            result = self.llm_client.generate_json(
                messages=messages,
                schema_model=JDRequirementSelection,
                temperature=0.0,
            )
        except Exception:
            return None

        # Guard against a model hallucinating an index we never sent it.
        selected = {i for i in result.requirement_line_indices if i in candidate_indices}
        # An empty selection out of a non-trivial candidate pool is a
        # stronger signal of a bad/degenerate LLM response than of a JD with
        # zero requirements — fall back to the heuristic rather than
        # silently returning an empty requirements list.
        if not selected and len(candidate_indices) >= 3:
            return None
        return selected

    def analyze(self, jd_text: str) -> JobDescription:
        lines = self._reflow_lines(jd_text)
        job_title = None
        company = None
        requirements: List[Requirement] = []
        preferred_section = False
        requirement_section = False

        # Every non-heading, non-metadata line is a candidate the LLM can
        # classify as requirement vs boilerplate. Metadata ("Job Title:",
        # "Company:") and section headings are always handled deterministically
        # below, regardless of LLM availability.
        candidate_indices: List[int] = []
        for idx, line in enumerate(lines):
            lowered = line.lower()
            if lowered.startswith(("job title:", "role:", "company:")):
                continue
            if self.HEADING_RE.match(line):
                continue
            candidate_indices.append(idx)

        llm_selected = self._llm_select_requirement_lines(lines, candidate_indices)

        for idx, line in enumerate(lines):
            lowered = line.lower()
            if lowered.startswith(("job title:", "role:")):
                job_title = line.split(":", 1)[1].strip()
                continue
            if lowered.startswith("company:"):
                company = line.split(":", 1)[1].strip()
                continue

            if self.HEADING_RE.match(line):
                preferred_section = any(signal in lowered for signal in self.PREFERRED_SIGNALS)
                requirement_section = any(token in lowered for token in (
                    "requirement", "qualification", "responsibilit", "skill", "who you are", "what you"
                ))
                continue

            was_bullet = bool(self.BULLET_LINE_RE.match(line))
            clean_line = self.BULLET_LINE_RE.sub("", line).strip()

            if llm_selected is not None:
                # LLM is the authority on inclusion when available — this is
                # what lets it exclude a bulleted "flexible PTO and great
                # snacks" perk line that the keyword heuristic below would
                # otherwise wrongly treat as a requirement just for being a
                # bullet.
                is_req = idx in llm_selected
            else:
                is_req = self._is_requirement(clean_line, was_bullet, requirement_section)
            if not is_req:
                continue

            priority = "preferred" if (
                preferred_section or any(signal in clean_line.lower() for signal in self.PREFERRED_SIGNALS)
            ) else "required"

            # Segment long or compound lines into atomic requirements
            segments = self._segment_line(clean_line)
            for seg in segments:
                requirements.append(Requirement(
                    id=f"req_{len(requirements) + 1:03d}",
                    text=seg, category=self._category(seg), priority=priority,
                ))

        return JobDescription(
            job_title=job_title or "Target Role",
            company=company or "Company",
            requirements=requirements,
            keywords=self.extract_keywords_from_text(jd_text),
            raw_text=jd_text,
        )

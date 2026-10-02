"""Tailored professional summary (P1.5).

Code decides the facts (years of experience from the role dates, the most
recent title, which JD skills the resume really shows, which lines hold
real results); one LLM call only phrases them. The result is a proposal
the user reviews like any bullet rewrite, and it is checked against the
whole resume: every term must appear in it and every number must come
from it (or be the computed years).
"""
import os
import re
from datetime import date
from typing import List, Optional
from uuid import uuid4

from app.analysis.change_proposal import ChangeProposal
from app.analysis.experience import years_of_experience, years_phrase
from app.analysis.rewriter import STATUS_LLM_ERROR, STATUS_LLM_UNAVAILABLE, STATUS_OK, STATUS_UNCHANGED, normalize_llm_text
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.report import KeywordMatchReport
from app.domain.resume import Resume
from app.llm.client import LLMClient
from app.llm.schemas import SummaryResult

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "summary.txt")
_NUMBER_RE = re.compile(r"\d")
MAX_SKILLS = 6
MAX_RESULT_LINES = 5
MAX_WORDS = 70


class SummaryWriter:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    # The resume's own claim of experience: "7 years", "5+ years", "10+ yrs".
    _YEARS_CLAIM_RE = re.compile(r"\b(\d{1,2}(?:\.\d)?\+?)\s*(?:years?|yrs?)\b", re.IGNORECASE)

    @staticmethod
    def sane_title(title: Optional[str]) -> bool:
        """A title fit to print (P8.10: a misread "03/" became the summary's
        first words): letters, no date fragments, not a sentence."""
        t = (title or "").strip()
        return (bool(re.search(r"[^\W\d_]{2}", t)) and not re.search(r"\d{1,2}/|\d{4}", t)
                and len(t.split()) <= 8 and not t.endswith(".") and len(t) <= 70)

    @classmethod
    def years_claim(cls, resume: Resume) -> Optional[str]:
        """The years the resume itself states, if it states any (open issue
        3: "4+ years" computed vs "3.6 years" written; sales 7 vs 10+)."""
        for text in (resume.summary, resume.candidate.headline):
            m = cls._YEARS_CLAIM_RE.search(text or "")
            if m:
                n = m.group(1)
                return f"{n} year" if n == "1" else f"{n} years"
        return None

    @classmethod
    def facts(cls, resume: Resume, keyword_report: KeywordMatchReport, today: Optional[date] = None) -> dict:
        """The inputs code decides; the LLM only phrases them."""
        roles = [r for e in resume.experience for r in e.all_roles() if r.title]
        found = sorted((r for r in keyword_report.rows if r.found), key=lambda r: (-r.weight, -r.jd_count))
        skills = [r.keyword for r in found if r.kind == "hard"][:MAX_SKILLS]
        credentials = [r.keyword for r in found if r.kind == "certification"][:MAX_SKILLS]
        results = [b.text for e in resume.experience for b in e.bullets if _NUMBER_RE.search(b.text)]
        projects = list(dict.fromkeys(b.group for e in resume.experience for b in e.bullets if b.group))
        title = next((r.title for r in roles if cls.sane_title(r.title)), None)
        if title is None and cls.sane_title(resume.candidate.headline):
            title = resume.candidate.headline
        return {
            "title": title or "",
            "years": cls.years_claim(resume) or years_phrase(years_of_experience(resume, today)),
            "skills": skills,
            "credentials": credentials,
            "results": results[:MAX_RESULT_LINES],
            "projects": projects,
        }

    def propose(
        self, resume: Resume, job: JobDescription, keyword_report: KeywordMatchReport,
        evidence: List[Evidence], today: Optional[date] = None,
    ) -> Optional[ChangeProposal]:
        """A summary proposal, or None when there's nothing to write from
        (no roles) or no LLM is configured."""
        if not resume.experience:
            return None
        facts = self.facts(resume, keyword_report, today)
        original = resume.summary or ""
        base = dict(
            id=f"prop_{uuid4().hex[:8]}", target_semantic_id="summary", target_source_location_id="summary",
            original_text=original, kind="summary",
            evidence_ids=[e.id for e in evidence if e.source_type == "summary"],
            # Facts the summary may state that aren't in the evidence ledger:
            # the computed years, role titles, project names.
            allowed_facts=[f for f in [facts["years"], *(r.title for e in resume.experience for r in e.all_roles()),
                                       *facts["projects"], *facts["skills"], *facts["credentials"]] if f],
            # A summary the user wrote stays unless they choose this one (P8.10).
            opt_in=bool(original.strip()),
            # (skills are verified by the keyword matcher, which knows
            # PySpark means Spark; the plain term check doesn't)
        )
        if not self.llm_client or not self.llm_client.is_available():
            reason = getattr(self.llm_client, "last_error", None) if self.llm_client else "no LLM configured"
            return ChangeProposal(**base, proposed_text=original, status=STATUS_LLM_UNAVAILABLE,
                                  error=reason or "LLM unavailable", rationale="Summary not tailored")
        with open(_PROMPT_PATH, encoding="utf-8") as f:
            system_prompt = f.read()
        user = "\n".join([
            f"Current summary: {original or '(none)'}",
            f"Most recent job title: {facts['title'] or '(not given)'}",
            f"Years of experience: {facts['years'] or 'under 1 year (do not state a number)'}",
            f"JD title: {job.job_title or '(not given)'}",
            "JD skills the resume shows: " + (", ".join(facts["skills"]) or "(none)"),
            "Licences / certifications the resume lists: " + (", ".join(facts["credentials"]) or "(none)"),
            "Resume lines with real results:",
            *[f"- {r}" for r in facts["results"]],
            "Project names: " + (", ".join(facts["projects"]) or "(none)"),
        ])
        try:
            result = self.llm_client.generate_json(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user}],
                schema_model=SummaryResult, temperature=0.2, effort="medium",
            )
        except Exception as e:
            return ChangeProposal(**base, proposed_text=original, status=STATUS_LLM_ERROR, error=str(e),
                                  rationale="Summary not tailored")
        text = normalize_llm_text(result.summary)
        words = len(text.split())
        if not text or words > MAX_WORDS:
            return ChangeProposal(**base, proposed_text=original, status=STATUS_LLM_ERROR,
                                  error=f"summary too long ({words} words)" if text else "empty summary",
                                  rationale="Summary not tailored")
        used = [s for s in result.skills_used if s in facts["skills"] and s.lower() in text.lower()]
        rationale = (f"Summary tailored to {job.job_title or 'the JD'}: "
                     f"{facts['years'] or 'experience'} as {facts['title'] or 'stated'}"
                     + (f"; skills: {', '.join(used)}" if used else "")
                     + (". Optional: your own summary stays unless you accept this one" if original.strip() else ""))
        status = STATUS_UNCHANGED if text.strip() == original.strip() else STATUS_OK
        return ChangeProposal(**base, proposed_text=text, status=status, rationale=rationale,
                              target_keywords=facts["skills"])

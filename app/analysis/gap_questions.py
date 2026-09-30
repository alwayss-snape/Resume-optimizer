"""Suggest-and-confirm gaps (P3.1): ask, never assume.

For JD lines whose keywords the resume doesn't show, the tool asks the
candidate whether they have that experience. Only what they confirm is
used: a ticked keyword goes into their skills, and a bullet is drafted
only from the words they typed. Questions are built in code (no LLM).
"""
from typing import Dict, List

from pydantic import BaseModel, Field

from app.analysis.keyword_match import _contains_seq, tokens
from app.domain.job import JobDescription
from app.domain.report import KeywordMatchReport

MAX_QUESTIONS = 6


class GapQuestion(BaseModel):
    id: str
    requirement: str  # the JD line, verbatim
    priority: str  # required | preferred
    keywords: List[str] = Field(default_factory=list)  # JD keywords the resume doesn't show
    question: str


class GapAnswer(BaseModel):
    question_id: str = ""
    confirmed_keywords: List[str] = Field(default_factory=list)  # ticked: "I have used this"
    answer: str = ""  # the candidate's own words; drafted into a bullet
    target: str = "auto"  # "auto", "new_project" or an experience id


def build_questions(job: JobDescription, report: KeywordMatchReport, limit: int = MAX_QUESTIONS) -> List[GapQuestion]:
    missing = [r for r in report.missing if r.kind in ("hard", "certification", "soft", "education")]
    questions: List[Dict] = []
    asked = set()
    for req in sorted(job.requirements, key=lambda r: r.priority != "required"):
        line = tokens(req.text)
        kws = [r for r in missing if r.keyword not in asked and _contains_seq(line, tokens(r.keyword))]
        if not kws:
            continue
        asked.update(r.keyword for r in kws)
        names = [r.keyword for r in kws]
        listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]
        questions.append({
            "requirement": req.text, "priority": req.priority, "keywords": names,
            "weight": sum(r.weight for r in kws),
            "question": f"The job asks for this. Have you worked with {listed}? Tick what you've really used, "
                        f"and if you like, describe where and how in your own words.",
        })
    questions.sort(key=lambda q: (q["priority"] != "required", -q["weight"]))
    return [GapQuestion(id=f"gap_{i + 1}", **{k: v for k, v in q.items() if k != "weight"})
            for i, q in enumerate(questions[:limit])]

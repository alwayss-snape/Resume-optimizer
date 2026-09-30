"""Skills tailoring (P1.6), deterministic: no LLM, nothing added.

The JD's skills move to the front of each category (and the category with
the most JD skills moves to the top), and a skill is renamed to the JD's
spelling only when it is the same term ("Numpy" -> "NumPy", an alias like
"machine learning" -> "ML"). A related but different term (PySpark vs
Spark) keeps its own name.
"""
import re
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.analysis.change_proposal import ChangeProposal
from app.analysis.keyword_match import KeywordMatcher, tokens
from app.domain.report import KeywordMatchReport
from app.domain.resume import Resume

SKILLS_TARGET = "skills"


def format_skills(skills: Dict[str, List[str]]) -> str:
    """One "Category: a, b, c" line per category (the editable form)."""
    return "\n".join(f"{cat}: {', '.join(items)}" for cat, items in skills.items())


def parse_skills(text: str) -> Dict[str, List[str]]:
    """Inverse of format_skills; a line without a label goes under "Skills"."""
    skills: Dict[str, List[str]] = {}
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        cat, _, items = line.partition(":") if ":" in line else ("Skills", "", line)
        values = [v.strip() for v in re.split(r",(?![^()]*\))", items) if v.strip()]
        if values:
            skills.setdefault(cat.strip() or "Skills", []).extend(values)
    return skills


def _key(term: str) -> str:
    return " ".join(tokens(term))


class SkillsTailor:
    def tailor(self, skills: Dict[str, List[str]], report: KeywordMatchReport) -> Dict[str, List[str]]:
        rows = [r for r in report.rows if r.kind in ("hard", "certification", "soft")]
        spelling: Dict[str, str] = {}
        for r in rows:
            spelling.setdefault(_key(r.keyword), r.keyword)

        matcher = KeywordMatcher()

        def score(item: str) -> Tuple[float, int]:
            # Same lookup as the match rate, so PySpark ranks as the JD's
            # "Spark" (it satisfies it) even though it keeps its own name.
            section = [("skill", tokens(item))]
            best = (0.0, 0)
            for r in rows:
                if matcher._find(r.keyword, section):
                    best = max(best, (r.weight, r.jd_count))
            return best

        tailored: Dict[str, List[str]] = {}
        for cat, items in skills.items():
            renamed = [spelling.get(_key(i), i) for i in items]
            order = sorted(range(len(renamed)), key=lambda i: (-score(items[i])[0], -score(items[i])[1], i))
            tailored[cat] = [renamed[i] for i in order]
        cat_weight = {cat: sum(score(i)[0] for i in items) for cat, items in skills.items()}
        cats = sorted(skills, key=lambda c: (-cat_weight[c], list(skills).index(c)))
        return {c: tailored[c] for c in cats}

    def propose(self, resume: Resume, report: KeywordMatchReport) -> Optional[ChangeProposal]:
        """A skills proposal, or None when nothing would change."""
        if not resume.skills:
            return None
        new = self.tailor(resume.skills, report)
        if new == resume.skills and list(new) == list(resume.skills):
            return None
        moved = [r.keyword for r in report.rows if r.found and r.kind == "hard"
                 and any(_key(r.keyword) == _key(i) for items in resume.skills.values() for i in items)]
        return ChangeProposal(
            id=f"prop_{uuid4().hex[:8]}", target_semantic_id=SKILLS_TARGET, target_source_location_id=SKILLS_TARGET,
            kind="skills", original_text=format_skills(resume.skills), proposed_text=format_skills(new),
            rationale="Skills reordered so the JD's come first" + (f": {', '.join(moved[:6])}" if moved else ""),
            status="ok", validation="PASS",
        )


def unknown_skills(original: Dict[str, List[str]], proposed: Dict[str, List[str]]) -> List[str]:
    """Skills in `proposed` that aren't in `original` under any spelling."""
    known = {_key(i) for items in original.values() for i in items}
    return [i for items in proposed.values() for i in items if _key(i) not in known]

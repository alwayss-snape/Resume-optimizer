"""The interview (P11.2): ask before writing, the way a good recruiter does.

Replaces guessing with questions tied to the candidate's own projects:
- a need of the job (from the role brief) that no kept project shows yet,
  asked about the project that comes closest ("Market Basket Analysis:
  did it involve prices, discounts or conversion ratios?");
- a kept project with no figure on it ("how many, how much, how much better?").
Questions are built in code from the brief and the plan (no AI call). The
answers are the candidate's own words: each becomes evidence of its project
and a bullet there, then goes through the usual rewrite and fact check.
"""
import re
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field

from app.analysis.project_select import competency_fit
from app.domain.evidence import Evidence
from app.domain.resume import Resume, ResumeBullet

MAX_NEED_QUESTIONS = 3
MAX_FIGURE_QUESTIONS = 2
MAX_ANSWER_CHARS = 600


class InterviewQuestion(BaseModel):
    id: str
    kind: str                        # "need" (a job need nothing shows yet) or "figure" (a project with no number)
    competency: str = ""
    experience_id: str = ""          # where the answer goes ("" for a need with no close project: the user picks)
    project: str = ""                # the project's heading ("" when asked about any job)
    job: str = ""                    # "Acme" for the card's heading
    question: str
    hint: str = ""                   # an example of a useful answer
    saved_answer: str = ""           # from an earlier application (profile)
    # Where the answer can go, for a need (P11.2): every project, and each job as a whole.
    options: List[Dict[str, str]] = Field(default_factory=list)  # {"experience_id", "project", "label"}


class InterviewAnswer(BaseModel):
    id: str
    answer: str = ""
    experience_id: str = ""          # the job the answer belongs to (a need: the user's choice)
    project: str = ""                # and its project; "" for the job as a whole


def _project_texts(resume: Resume, notes: Dict[str, List[str]]) -> List[Tuple[str, str, str, List[str]]]:
    """(key, experience id, project, texts) for every project of every job."""
    out = []
    for e in resume.experience:
        for name, bullets in e.bullet_groups():
            if name:
                key = f"{e.id}::{name}"
                out.append((key, e.id, name, [name, *(b.text for b in bullets), *notes.get(key, [])]))
    return out


def build_interview(resume: Resume, brief, plan_projects: Sequence, embedder=None,
                    notes: Optional[Dict[str, List[str]]] = None) -> List[InterviewQuestion]:
    notes = notes or {}
    companies = {e.id: e.company or e.title or "your job" for e in resume.experience}
    projects = _project_texts(resume, notes)
    questions: List[InterviewQuestion] = []

    # 1. Needs nothing kept shows yet: stated ones first, in the brief's order.
    if brief is not None and brief.competencies:
        left_out = {c.key for c in plan_projects if not c.chosen}
        mapped = getattr(brief, "project_evidence", {}) or {}
        shown = {x["competency"] for key, links in mapped.items() if key not in left_out for x in links}
        missing = [c for c in sorted(brief.competencies, key=lambda c: c.kind != "stated") if c.name not in shown]
        fit = competency_fit([p[3] for p in projects], brief, embedder) if projects else []
        names = [c.name for c in brief.competencies]
        options = [{"experience_id": p[1], "project": p[2], "label": f"{p[2]} ({companies.get(p[1], '')})"}
                   for p in projects]
        options += [{"experience_id": e.id, "project": "", "label": f"Elsewhere at {companies[e.id]}"}
                    for e in resume.experience]
        for comp in missing[:MAX_NEED_QUESTIONS]:
            examples = ", ".join(comp.look_for[:3])
            ci = names.index(comp.name)
            # A guess to start the choice from; the question never claims it.
            best = max(range(len(projects)), key=lambda p: fit[p][ci]) if projects else None
            guess = projects[best] if best is not None and fit[best][ci] > 0 else None
            questions.append(InterviewQuestion(
                id=f"need_{len(questions)}", kind="need", competency=comp.name,
                experience_id=guess[1] if guess else (resume.experience[0].id if resume.experience else ""),
                project=guess[2] if guess else "", job=companies.get(guess[1], "") if guess else "",
                question=(f"The job needs {comp.name.lower()}, and none of your work shows it yet. Have you done "
                          f"anything like {examples}? If so, where, what did you do, and what changed as a result?"),
                hint="e.g. Set the delivery fee tiers for 40 stores; orders rose about 6%. "
                     "Skip it if you haven't: nothing is added without your answer.",
                options=options))

    # 2. Kept projects with no figure: the current job first.
    kept = {c.key for c in plan_projects if c.chosen}
    choosing = {c.experience_id for c in plan_projects}
    figures = 0
    for index, e in enumerate(resume.experience):
        if figures >= MAX_FIGURE_QUESTIONS:
            break
        for name, bullets in e.bullet_groups():
            key = f"{e.id}::{name}"
            if not name or (e.id in choosing and key not in kept):
                continue
            text = " ".join([b.text for b in bullets] + notes.get(key, []))
            if _has_number(text) or figures >= MAX_FIGURE_QUESTIONS:
                continue
            figures += 1
            questions.append(InterviewQuestion(
                id=f"figure_{figures}", kind="figure", experience_id=e.id, project=name, job=companies.get(e.id, ""),
                question=(f"{name} has no number on it yet. What can you put a number on: how many (users, models, "
                          "pipelines), how much (money, hours saved) or how much better (accuracy, speed)?"),
                hint="e.g. Watches 30 nightly jobs; cut the time to find a failure from a day to an hour."))
    return questions


def _has_number(text: str) -> bool:
    """Any figure but a year ("500 stores", "3 packages", "60%")."""
    return any(not re.fullmatch(r"(?:19|20)\d{2}", n) for n in re.findall(r"\d[\d,.]*\d|\d", text or ""))


def _clean_answer(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()[:MAX_ANSWER_CHARS]
    return text.rstrip()


def apply_interview(resume: Resume, evidence: List[Evidence], brief, questions: Sequence[InterviewQuestion],
                    answers: Sequence[InterviewAnswer]) -> List[str]:
    """Each answer becomes a bullet of its project (or job) in the
    candidate's own words, with evidence; a need answered for a project
    counts as that project showing it. Returns notes for the run log."""
    by_id = {q.id: q for q in questions}
    jobs = {e.id: e for e in resume.experience}
    notes: List[str] = []
    for a in answers:
        q = by_id.get(a.id)
        text = _clean_answer(a.answer)
        if not q or not text:
            continue
        # A need's answer goes where the user said; a figure's to its project.
        exp_id, project = ((a.experience_id, a.project) if q.kind == "need" and a.experience_id
                           else (q.experience_id, q.project))
        exp = jobs.get(exp_id) or (resume.experience[0] if resume.experience else None)
        if exp is None:
            continue
        group = project if project and any(b.group == project for b in exp.bullets) else None
        bid = f"{exp.id}_q{uuid4().hex[:6]}"
        bullet = ResumeBullet(id=bid, text=text, group=group)
        # After the project's last bullet, so it reads as part of it.
        last = max((i for i, b in enumerate(exp.bullets) if b.group == group), default=len(exp.bullets) - 1)
        exp.bullets.insert(last + 1, bullet)
        evidence.append(Evidence(id=f"ev_answer_{uuid4().hex[:6]}", source_type="experience", source_id=bid,
                                 text=f"{exp.company}: {text}"))
        if q.kind == "need" and group and brief is not None:
            key = f"{exp.id}::{group}"
            links = brief.project_evidence.setdefault(key, [])
            if all(x["competency"] != q.competency for x in links):
                links.append({"competency": q.competency, "quote": text[:120]})
        notes.append(f"Added your answer to {group or exp.company}" + (f" ({q.competency})" if q.competency else ""))
    return notes

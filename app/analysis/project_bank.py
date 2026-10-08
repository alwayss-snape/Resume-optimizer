"""A project bank as a document (P11.1).

The owner's own notes about their work (jobs, projects, bullets, overviews,
tech lists, figures, "to verify" items) read next to the resume. The AI only
says what each line is, by number; code keeps every line's words as written,
checks every index, and merges the result into the parsed resume: new jobs
are added, new projects join their job, notes become evidence of their
project (never bullets), and "to verify" lines are held back and listed.
"""
import os
import re
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field

from app.domain.evidence import Evidence
from app.domain.resume import Experience, Resume, ResumeBullet, Role
from app.llm.schemas import BankStructure

MAX_BANK_LINES = 400
_NUMBERING = re.compile(r"^\s*(?:[A-Z]?\d+(?:\.\d+)*[.)]?|[-*•●▪◦])\s+")
_STOP = {"the", "a", "an", "of", "and", "company", "companies", "inc", "ltd", "llc", "group", "pvt", "private",
         "limited", "corp", "corporation", "a publicis groupe company"}


class BankProjectNotes(BaseModel):
    name: str
    bullets: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class BankJobNotes(BaseModel):
    company: str
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    projects: List[BankProjectNotes] = Field(default_factory=list)


class Bank(BaseModel):
    jobs: List[BankJobNotes] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    to_verify: List[str] = Field(default_factory=list)


def bank_lines(text: str) -> List[str]:
    lines = [re.sub(r"\s+", " ", l).strip() for l in (text or "").splitlines()]
    return [l for l in lines if l][:MAX_BANK_LINES]


def _clean(line: str) -> str:
    return _NUMBERING.sub("", line).strip()


def read_bank(lines: List[str], llm_client) -> Optional[Bank]:
    """The bank's structure, or None when there's no AI or its answer can't
    be used (the person is told and can paste notes under a job instead)."""
    if not lines or not llm_client or not llm_client.is_available():
        return None
    path = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "read_bank.txt")
    with open(path, "r", encoding="utf-8") as f:
        system = f.read()
    numbered = "\n".join(f"{i}: {l}" for i, l in enumerate(lines))
    try:
        result: BankStructure = llm_client.generate_json(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": f"Numbered lines:\n{numbered}"}],
            schema_model=BankStructure, temperature=0.0, effort="medium")
    except Exception:
        return None
    return structure_to_bank(lines, result)


def _verbatim(value: str, text: str) -> str:
    """A value the model returned, kept only if the notes say it."""
    value = (value or "").strip()
    return value if value and value.lower() in text.lower() else ""


def structure_to_bank(lines: List[str], s: BankStructure) -> Optional[Bank]:
    """Check every index and value against the notes; build the bank from
    the notes' own lines."""
    n = len(lines)
    ok = lambda i: isinstance(i, int) and 0 <= i < n
    text = "\n".join(lines)
    verify = {i for i in s.to_verify_lines if ok(i)}
    bullets = {i for i in s.bullet_lines if ok(i)} - verify
    achievements = [i for i in s.achievement_lines if ok(i) and i not in verify]
    skills = [i for i in s.skill_lines if ok(i)]
    bank = Bank()
    jobs: List[Optional[BankJobNotes]] = []
    for j in s.jobs:
        company = _verbatim(j.company, text)
        if not company or not ok(j.line):
            jobs.append(None)
            continue
        end = "Present" if (j.end_date or "").strip().lower() in ("present", "current", "now") else _verbatim(j.end_date, text)
        jobs.append(BankJobNotes(company=company, title=_verbatim(j.title, text),
                                 start_date=_verbatim(j.start_date, text), end_date=end))
    used = set(achievements) | set(skills)
    for p in sorted(s.projects, key=lambda p: p.heading_line):
        if not (ok(p.heading_line) and ok(p.last_line) and 0 <= p.job < len(jobs) and jobs[p.job]):
            continue
        heading = _clean(lines[p.heading_line]).rstrip(":")
        name = _verbatim(p.name, heading) or heading
        if not name or len(name.split()) > 12:
            continue
        project = BankProjectNotes(name=name)
        for i in range(p.heading_line + 1, min(p.last_line, n - 1) + 1):
            if i in used or i in verify:
                continue
            used.add(i)
            (project.bullets if i in bullets else project.notes).append(_clean(lines[i]))
        if not project.bullets and project.notes:
            # Notes only (an overview, a plan): its own lines are its bullets, a few at most.
            work = [l for l in project.notes if not re.match(r"^(?:tech|tools|stack|key numbers|note)s?\s*:", l, re.I)]
            project.bullets, project.notes = work[:4], [l for l in project.notes if l not in work[:4]]
        if project.bullets or project.notes:
            jobs[p.job].projects.append(project)
    bank.jobs = [j for j in jobs if j and j.projects]
    bank.achievements = [_clean(lines[i]) for i in achievements]
    bank.skills = [_clean(lines[i]) for i in skills]
    bank.to_verify = [_clean(lines[i]) for i in sorted(verify)]
    return bank if bank.jobs or bank.achievements else None


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in _STOP and len(t) > 1}


def _same_company(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb and (ta <= tb or tb <= ta or len(ta & tb) >= 2))


def _same_text(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / min(len(ta), len(tb)) >= 0.8


def _same_project(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / min(len(ta), len(tb)) >= 0.6


def merge_bank(resume: Resume, evidence: List[Evidence], bank: Bank,
               new_experience=None) -> List[str]:
    """Merge the bank into the parsed resume, in place. Returns plain notes
    for Check details ("From your notes: ..."). `new_experience(role_data)`
    makes and validates a job the resume doesn't have (the service's
    "add a job" path); a job it rejects (no dates) is skipped with a note."""
    notes: List[str] = []
    for job in bank.jobs:
        exp = next((e for e in resume.experience if _same_company(e.company, job.company)), None)
        added_job = exp is None
        if added_job:
            if new_experience is None:
                continue
            try:
                exp = new_experience({"company": job.company, "title": job.title, "start_date": job.start_date,
                                      "end_date": job.end_date, "current": job.end_date == "Present"})
            except ValueError as e:
                notes.append(f"Not added from your notes: {job.company} ({e})")
                continue
        elif job.end_date and job.end_date != "Present" and exp.end_date and exp.end_date.lower() == "present":
            # The resume still says "Present"; the notes give the end date.
            exp.end_date = job.end_date
            if exp.roles:
                exp.roles[0] = Role(title=exp.roles[0].title, start_date=exp.roles[0].start_date, end_date=job.end_date)
            notes.append(f"{exp.company}: end date set to {job.end_date} from your notes")
        new_projects, enriched = [], []
        for project in job.projects:
            groups = [g for g, _ in exp.bullet_groups() if g]
            group = next((g for g in groups if _same_project(g, project.name)), None)
            existing = [b.text for b in exp.bullets if group and b.group == group]
            target = group or project.name
            n = len(exp.bullets)
            for line in project.bullets:
                if any(_same_text(line, t) for t in existing):
                    continue  # already on the resume
                n += 1
                bid = f"{exp.id}_k{n:02d}_{uuid4().hex[:4]}"
                exp.bullets.append(ResumeBullet(id=bid, text=line, group=target))
                evidence.append(Evidence(id=f"ev_bank_{uuid4().hex[:6]}", source_type="experience", source_id=bid,
                                         text=f"{exp.company}: {line}"))
            # Notes are evidence of the project, never bullets (P11.5 writes from them).
            for line in project.notes:
                evidence.append(Evidence(id=f"ev_bank_{uuid4().hex[:6]}", source_type="general",
                                         source_id=f"{exp.id}::{target}", text=line))
            if not any(b.group == target for b in exp.bullets):
                continue  # notes only, nothing to show
            (enriched if group else new_projects).append(target)
        if added_job:
            if exp.bullets:
                resume.experience.append(exp)
                notes.append(f"Added {exp.company} from your notes, with {len(new_projects)} project(s)")
            continue
        if new_projects:
            notes.append(f"{exp.company}: {len(new_projects)} project(s) added from your notes")
        if enriched:
            notes.append(f"{exp.company}: your notes add detail to {len(enriched)} project(s) already on the resume")
    for line in bank.achievements:
        if not any(_same_text(line, a) for a in resume.achievements):
            resume.achievements.append(line)
            evidence.append(Evidence(id=f"ev_bank_{uuid4().hex[:6]}", source_type="achievement",
                                     source_id="bank_achievement", text=line))
    for line in bank.skills:
        evidence.append(Evidence(id=f"ev_bank_{uuid4().hex[:6]}", source_type="skill", source_id="bank_skills", text=line))
    if bank.to_verify:
        notes.append(f"Held back {len(bank.to_verify)} line(s) your notes mark to verify; they're not used")
    return notes

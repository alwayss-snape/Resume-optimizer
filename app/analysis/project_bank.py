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


CHUNK_LINES = 90      # a large bank is read in parts of this many lines ...
CONTEXT_LINES = 12    # ... each with the bank's opening lines (where the jobs are usually listed)


def read_bank(lines: List[str], llm_client) -> Optional[Bank]:
    """The bank's structure, or None when there's no AI or its answer can't
    be used (the person is told and can paste notes under a job instead).
    A large bank whose answer runs out of room is read in parts (as P10.10
    did for long roles): the owner's 2026-10-09 bank failed whole twice."""
    if not lines or not llm_client or not llm_client.is_available():
        return None
    path = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "read_bank.txt")
    with open(path, "r", encoding="utf-8") as f:
        system = f.read()

    def ask(indices: List[int]) -> Optional[BankStructure]:
        numbered = "\n".join(f"{i}: {lines[i]}" for i in indices)
        try:
            return llm_client.generate_json(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": f"Numbered lines:\n{numbered}"}],
                schema_model=BankStructure, temperature=0.0, effort="low")
        except Exception:
            return None

    # One call for a small bank; a large one goes straight to parts (Groq's free
    # tier refuses a 190-line bank outright: "Request too large").
    if len(lines) <= SINGLE_CALL_LINES:
        whole = ask(list(range(len(lines))))
        if whole is not None:
            return structure_to_bank(lines, whole)
    parts = []
    for span, extra in bank_parts(lines):
        context = [i for i in range(min(CONTEXT_LINES, len(lines))) if i < span[0]] + extra
        got = ask(sorted(set(context)) + list(span))
        if got is not None:
            parts.append((set(span), got))
    if not parts:
        return None
    return structure_to_bank(lines, merge_structures(lines, parts))


SINGLE_CALL_LINES = 100


def bank_parts(lines: List[str]):
    """(line span, extra context lines) per part: split where a job starts
    (a short line with a date range: "Part B — Acme (Aug 2022 – Mar 2026)"),
    then a long job into pieces that keep its heading as context, so a part
    never mixes the end of one job with the start of another."""
    starts = [i for i, l in enumerate(lines) if _RANGE.search(l) and len(l.split()) <= 14 and i > 0]
    bounds = sorted(set([0] + starts + [len(lines)]))
    out = []
    for a, b in zip(bounds, bounds[1:]):
        for piece in range(a, b, CHUNK_LINES):
            span = list(range(piece, min(b, piece + CHUNK_LINES)))
            out.append((span, [a] if piece > a else []))
    # Tiny sections (a snapshot line, a lone heading) join the next part.
    merged = []
    for span, extra in out:
        if merged and len(merged[-1][0]) < 8:
            prev_span, prev_extra = merged.pop()
            span, extra = prev_span + span, prev_extra + extra
        merged.append((span, extra))
    return merged


def merge_structures(lines: List[str], parts) -> BankStructure:
    """Parts read separately, as one: jobs matched by company, each part's
    projects and line lists kept for the lines that part was reading."""
    merged = BankStructure()
    for span, part in parts:
        index_of = {}
        for k, job in enumerate(part.jobs):
            same = next((n for n, j in enumerate(merged.jobs) if _same_company(j.company, job.company)), None)
            if same is None:
                merged.jobs.append(job)
                same = len(merged.jobs) - 1
            index_of[k] = same
        for proj in part.projects:
            if proj.heading_line in span and proj.job in index_of:
                merged.projects.append(proj.model_copy(update={"job": index_of[proj.job]}))
        for name in ("bullet_lines", "to_verify_lines", "achievement_lines", "skill_lines"):
            getattr(merged, name).extend(i for i in getattr(part, name) if i in span)
    return merged


_DATE = r"(?:[A-Z][a-z]{2,8}\.?\s+)?(?:19|20)\d{2}"
_RANGE = re.compile(rf"({_DATE})\s*(?:–|-|—|to)\s*({_DATE}|Present|Current|Now)", re.I)
_NOT_BUILT = re.compile(r"\b(?:concept|idea|proposal|proposed|planned|poc|proof of concept|exploring|exploration|"
                        r"to verify|tbd|draft)\b", re.I)
_QUOTED = re.compile(r"[\"“]([^\"”]{3,60})[\"”]")
_CORRECTED = re.compile(r"\bnot\s+((?:[A-Z][\w+#-]*\s?){2,6})")
_DOUBT = re.compile(r"\b(?:to verify|verify|confirm|unconfirmed|tbd|to add|not sure|check)\b", re.I)


def doubted_lines(lines: List[str], verify: set, projects) -> set:
    """Lines the notes themselves doubt, whatever the AI said (P11.1): the
    owner's 2026-10-09 run printed an unbuilt "(Concept)" project as done
    and kept a figure a "to verify" note questioned and a platform a note
    said was wrong. Held back: a project whose heading says it isn't built
    (concept, idea, proposal, planned, POC, exploring); any line holding a
    phrase a doubting line quotes ("hours to seconds"); any line naming what a
    note corrects ("..., not Platform X")."""
    n = len(lines)
    out = set()
    for p in projects:
        if 0 <= p.heading_line < n and _NOT_BUILT.search(lines[p.heading_line]):
            out |= set(range(p.heading_line, min(p.last_line, n - 1) + 1))
    doubting = [lines[i] for i in range(n) if i in verify or _DOUBT.search(lines[i])]
    phrases = {m.group(1).strip().lower() for l in doubting for m in _QUOTED.finditer(l)}
    phrases |= {m.group(1).strip().lower() for l in lines for m in _CORRECTED.finditer(l)
                if re.search(r"\b(?:note|use|instead|actually|revised|wrong|correct)", l, re.I)}
    phrases = {ph for ph in phrases if len(ph.split()) >= 2 or len(ph) >= 6}
    for i, line in enumerate(lines):
        low = line.lower()
        if any(ph in low for ph in phrases) and i not in out:
            # The doubting note itself and lines that merely repeat the correction stay out too.
            out.add(i)
    return out


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
    verify |= doubted_lines(lines, verify, s.projects)
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
        start = _verbatim(j.start_date, text)
        if not (start and end):  # the job's own line says it: "Acme (August 2022 – March 2026)"
            m = _RANGE.search(lines[j.line])
            if m:
                start = start or m.group(1)
                end = end or ("Present" if m.group(2).lower() in ("present", "current", "now") else m.group(2))
        jobs.append(BankJobNotes(company=company, title=_verbatim(j.title, text), start_date=start, end_date=end))
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

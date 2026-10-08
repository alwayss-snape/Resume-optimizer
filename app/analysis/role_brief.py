"""Role brief (P11.3): what the job really needs, before choosing or writing.

A two-sentence post ("pricing, yield optimization and inventory management…")
names few keywords but implies more: demand forecasting, experimentation,
optimization. One AI call reads the JD as a recruiter would; code keeps a
competency only when the JD words it rests on are really in the JD. Inferred
competencies steer project choice and the interview, never the match score.
Without the AI, the brief is the JD's own title and skills.
"""
import os
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.domain.job import JobDescription
from app.domain.resume import Resume
from app.llm.schemas import RoleBriefResult

MAX_COMPETENCIES = 6


class Competency(BaseModel):
    name: str
    kind: str = "stated"          # "stated" or "inferred"
    jd_words: str = ""
    look_for: List[str] = Field(default_factory=list)


class RoleBrief(BaseModel):
    target_title: str = ""
    competencies: List[Competency] = Field(default_factory=list)
    positioning: str = ""
    source: str = "heuristic"     # "llm" or "heuristic"
    headline: str = ""            # P11.6: the target title as far as the candidate's titles support it
    # P11.4: "<job id>::<project>" -> [{"competency", "quote"}], the
    # competencies each project really shows, with its own words as proof.
    project_evidence: Dict[str, List[Dict[str, str]]] = Field(default_factory=dict)

    def terms(self) -> List[str]:
        """Every competency's name and look-for words, for matching projects."""
        out: List[str] = []
        for c in self.competencies:
            for t in [c.name, *c.look_for]:
                if t and t.lower() not in (x.lower() for x in out):
                    out.append(t)
        return out


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def resume_overview(resume: Resume, limit: int = 1400) -> str:
    """Jobs and project names with a line each, for the positioning sentence."""
    parts = []
    for e in resume.experience:
        parts.append(f"{e.title or ''} at {e.company or ''}".strip())
        for name, bullets in e.bullet_groups():
            first = bullets[0].text if bullets else ""
            parts.append(f"- {name + ': ' if name else ''}{first[:140]}")
    if resume.summary:
        parts.insert(0, resume.summary[:300])
    return "\n".join(parts)[:limit]


def fallback_brief(job_desc: JobDescription) -> RoleBrief:
    skills = [k for k in (job_desc.hard_skills or job_desc.keywords) if k and k.lower() != "data"]
    return RoleBrief(target_title=job_desc.job_title or "",
                     competencies=[Competency(name=k, kind="stated", jd_words=k, look_for=[k.lower()])
                                   for k in skills[:MAX_COMPETENCIES]])


def write_brief(job_desc: JobDescription, resume: Resume, llm_client) -> RoleBrief:
    if not llm_client or not llm_client.is_available() or not (job_desc.raw_text or "").strip():
        return fallback_brief(job_desc)
    path = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "role_brief.txt")
    with open(path, "r", encoding="utf-8") as f:
        system = f.read()
    user = f"Job description:\n{job_desc.raw_text}\n\nResume overview:\n{resume_overview(resume)}"
    try:
        result: RoleBriefResult = llm_client.generate_json(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            schema_model=RoleBriefResult, temperature=0.0, effort="medium")
    except Exception:
        return fallback_brief(job_desc)
    return checked_brief(result, job_desc)


def checked_brief(result: RoleBriefResult, job_desc: JobDescription) -> RoleBrief:
    """Keep what the JD backs: a competency's JD words must be in the JD; a
    title must be the JD's. Look-for words are short and lower case."""
    jd = _norm(job_desc.raw_text)
    title = (result.target_title or "").strip()
    if not title or _norm(title) not in jd:
        title = job_desc.job_title or ""
    competencies: List[Competency] = []
    for c in result.competencies:
        name = (c.name or "").strip()
        words = (c.jd_words or "").strip()
        if not name or len(name.split()) > 6 or not words or _norm(words) not in jd:
            continue
        if any(_norm(name) == _norm(x.name) for x in competencies):
            continue
        look = [w.strip().lower() for w in c.look_for if w.strip() and len(w.split()) <= 4][:8]
        kind = "stated" if _norm(name) in jd or c.kind == "stated" else "inferred"
        competencies.append(Competency(name=name, kind=kind, jd_words=words, look_for=look or [name.lower()]))
    if not competencies:
        return fallback_brief(job_desc)
    positioning = re.sub(r"\s+", " ", result.positioning or "").strip()
    if len(positioning.split()) > 30:
        positioning = ""
    return RoleBrief(target_title=title, competencies=competencies[:MAX_COMPETENCIES], positioning=positioning,
                     source="llm")


def map_projects(brief: RoleBrief, resume: Resume, notes: Dict[str, List[str]], llm_client) -> RoleBrief:
    """Which competencies each project really shows (P11.4), in one AI call.
    A link is kept only when its quote is the project's own words and the
    competency is the brief's. Without the AI the map stays empty and
    selection falls back to embeddings."""
    if brief.source != "llm" or not llm_client or not llm_client.is_available():
        return brief
    projects = []  # (key, texts)
    for e in resume.experience:
        groups = [(n, bs) for n, bs in e.bullet_groups() if n]
        if len(groups) < 2:
            continue
        for name, bullets in groups:
            key = f"{e.id}::{name}"
            projects.append((key, [name, *(b.text for b in bullets), *notes.get(key, [])]))
    if not projects:
        return brief
    path = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "project_evidence.txt")
    with open(path, "r", encoding="utf-8") as f:
        system = f.read()
    comps = "\n".join(f"- {c.name} (look for: {', '.join(c.look_for)})" for c in brief.competencies)
    listing = []
    for i, (_, texts) in enumerate(projects):
        listing.append(f"{i}. {texts[0]}")
        listing += [f"   - {t[:260]}" for t in texts[1:8]]
    user = f"The job's competencies:\n{comps}\n\nProjects:\n" + "\n".join(listing)
    try:
        from app.llm.schemas import ProjectEvidenceResult
        result = llm_client.generate_json(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            schema_model=ProjectEvidenceResult, temperature=0.0, effort="medium")
    except Exception:
        return brief
    names = {_norm(c.name): c.name for c in brief.competencies}
    out: Dict[str, List[Dict[str, str]]] = {}
    for item in result.projects:
        if not 0 <= item.project < len(projects):
            continue
        key, texts = projects[item.project]
        text = _norm(" ".join(texts))
        for shown in item.shows:
            comp = names.get(_norm(shown.competency))
            quote = (shown.quote or "").strip().strip('"')
            if comp and quote and len(quote.split()) >= 2 and _norm(quote) in text:
                if all(x["competency"] != comp for x in out.get(key, [])):
                    out.setdefault(key, []).append({"competency": comp, "quote": quote})
    return brief.model_copy(update={"project_evidence": out})


def with_headline(brief: RoleBrief, job_desc: JobDescription, resume: Resume) -> RoleBrief:
    """The headline under the name (P11.6): the job's title as far as the
    candidate's own titles support it; confirmed or changed on Review."""
    from app.analysis.summary_writer import SummaryWriter
    title = SummaryWriter.evidenced_title(brief.target_title or job_desc.job_title, resume)
    return brief.model_copy(update={"headline": title})

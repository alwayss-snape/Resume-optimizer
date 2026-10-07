"""Arrange and edit before download (P8.13–P8.16).

After tailoring, the user owns the final structure: section order, which
sections show, the order of jobs, projects and degrees, the order of each
job's bullets, a bullet's text, and what page-fit may trim. All of it is a
`Layout` applied by code to the tailored resume as it was *before* page-fit
(so anything trimmed can come back); nothing here calls the LLM.

Two rules keep the core promise:
- a bullet only moves within its own job or project, never into another
  one (a fact under the wrong job is what the user test found most
  harmful);
- the user's own text is theirs (user-attested, as in review), but a new
  number or tool is pointed out.
"""
import copy
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.analysis.experience import parse_month
from app.domain.resume import Resume
from app.rendering.layout import SECTION_TITLES, date_range, display_skills, format_date_text, other_section

# Sections the template prints, in the keys `presentation.section_order` uses.
STANDARD = ("summary", "experience", "skills", "education", "projects", "certifications", "achievements", "interests")


class Layout(BaseModel):
    section_order: List[str] = Field(default_factory=list)
    hidden_sections: List[str] = Field(default_factory=list)
    # "experience" / "projects" / "education" -> entry ids in order
    entry_order: Dict[str, List[str]] = Field(default_factory=dict)
    # job or project id -> its bullet ids in order (only its own bullets)
    bullet_order: Dict[str, List[str]] = Field(default_factory=dict)
    removed_bullets: List[str] = Field(default_factory=list)  # taken out by the user
    edits: Dict[str, str] = Field(default_factory=dict)  # bullet id -> the user's text
    # Bullet ids, project ids or "interests" page-fit must leave in (restored).
    pinned: List[str] = Field(default_factory=list)
    page_target: Optional[int] = None  # None: by years of experience
    trim: bool = True  # False: "don't trim", render at full length
    region: Optional[str] = None  # P10.3: "us", "uk_eu", "india", "other"; None keeps the run's
    cv_mode: Optional[str] = None  # P10.5: "standard", "academic", "federal"; None keeps the run's


def _owners(resume: Resume):
    return [*resume.experience, *resume.projects]


def default_layout(full: Resume, section_order: List[str]) -> Layout:
    """The layout tailoring produced: everything shown, in its current order."""
    return Layout(
        section_order=list(section_order),
        entry_order={"experience": [e.id for e in full.experience], "projects": [p.id for p in full.projects],
                     "education": [e.id for e in full.education]},
        bullet_order={o.id: [b.id for b in o.bullets] for o in _owners(full)},
    )


def _ordered(items: list, order: List[str]) -> list:
    """Items in `order`; any not listed keep their place after the listed ones."""
    rank = {i: n for n, i in enumerate(order or [])}
    return sorted(items, key=lambda it: rank.get(it.id, len(rank) + items.index(it)))


def _keep_groups_together(bullets: List) -> List:
    """A sub-heading's bullets stay together (R3): whatever order arrives, a
    group sits where its first bullet is, so a project heading is never split
    in two by a bullet moved out of it."""
    groups: Dict = {}
    for b in bullets:
        groups.setdefault(b.group or "", []).append(b)
    return [b for group in groups.values() for b in group]


def apply_layout(full: Resume, layout: Layout) -> Resume:
    """A copy of `full` arranged as `layout` says. Unknown ids are ignored;
    a bullet listed under another owner stays with its own owner."""
    resume = copy.deepcopy(full)
    removed = set(layout.removed_bullets)
    for owner in _owners(resume):
        own = {b.id for b in owner.bullets}
        order = [bid for bid in layout.bullet_order.get(owner.id, []) if bid in own]
        owner.bullets = [b for b in _keep_groups_together(_ordered(owner.bullets, order)) if b.id not in removed]
        for b in owner.bullets:
            text = (layout.edits.get(b.id) or "").strip()
            if text:
                b.text = text
    # A job or project whose every bullet the user took out is left out
    # whole: a title with nothing under it doesn't read back (Stage J review).
    resume.experience = [e for e in resume.experience if e.bullets or not _had_bullets(full, e.id)]
    resume.projects = [p for p in resume.projects if p.bullets or not _had_bullets(full, p.id)]
    resume.experience = _ordered(resume.experience, layout.entry_order.get("experience", []))
    resume.projects = _ordered(resume.projects, layout.entry_order.get("projects", []))
    resume.education = _ordered(resume.education, layout.entry_order.get("education", []))
    hidden = set(layout.hidden_sections)
    if "summary" in hidden:
        resume.summary = None
    for key in ("experience", "projects", "education", "certifications", "achievements", "interests"):
        if key in hidden:
            setattr(resume, key, [])
    if "skills" in hidden:
        resume.skills = {}
    resume.other_sections = [s for s in resume.other_sections if f"other:{s.id}" not in hidden]
    return resume


def _had_bullets(full: Resume, owner_id: str) -> bool:
    return any(o.id == owner_id and o.bullets for o in _owners(full))


def emptied(full: Resume, layout: Layout) -> List[str]:
    """Jobs and projects the user took every bullet out of."""
    removed = set(layout.removed_bullets)
    return [o.id for o in _owners(full) if o.bullets and all(b.id in removed for b in o.bullets)]


def section_order(layout: Layout, resume: Resume) -> List[str]:
    """The render order: the user's order, then anything it doesn't list."""
    keys = list(dict.fromkeys(k for k in layout.section_order if k in STANDARD or k.startswith("other:")))
    extra = [k for k in STANDARD if k not in keys] + [f"other:{s.id}" for s in resume.other_sections
                                                      if f"other:{s.id}" not in keys]
    return keys + extra


def notes_for(layout: Layout, full: Resume, original: Resume) -> List[str]:
    """Things worth pointing out about the user's arrangement. Advice only."""
    notes: List[str] = []
    jobs = {e.id: e for e in full.experience}
    order = [jobs[i] for i in layout.entry_order.get("experience", []) if i in jobs]

    def start(exp):
        roles = exp.all_roles()
        return parse_month(roles[0].start_date if roles else None, is_end=False, today=_today()) or (0, 0)

    starts = [start(e) for e in order]
    if any(a < b for a, b in zip(starts, starts[1:]) if a != (0, 0) and b != (0, 0)):
        notes.append("Your jobs are no longer newest first; most recruiters expect that order.")
    numbers = lambda text: {n.rstrip(",.") for n in re.findall(r"\d[\d,.]*%?", text or "")}
    known_numbers = numbers(" ".join(_all_text(original)))
    owners = {o.id: o for o in _owners(full)}
    for owner_id in emptied(full, layout):
        o = owners[owner_id]
        name = getattr(o, "company", None) or getattr(o, "name", "") or "an entry"
        notes.append(f"Every bullet of {name} is taken out, so it's left out of the file. Put a bullet back to show it.")
    for bid, text in layout.edits.items():
        new = sorted(numbers(text) - known_numbers)
        if new:
            notes.append(f"Your edit adds {', '.join(new)}, which isn't elsewhere in your resume: make sure it's "
                         "right before you send it.")
    return notes


def _today():
    from datetime import date
    return date.today()


def _all_text(resume: Resume) -> List[str]:
    out = [resume.summary or ""]
    for o in _owners(resume):
        out += [b.text for b in o.bullets]
    return out


def view(full: Resume, original: Resume, layout: Layout, trimmed: List[Dict], default: Optional[Layout] = None) -> Dict:
    """What the Arrange screen shows: every section with its entries and
    bullets (ids, text, the AI's text and the file's text), the original
    order for "Restore my original order", and what page-fit trimmed."""
    original_text = {b.id: b.text for o in _owners(original) for b in o.bullets}
    source_order = {o.id: [b.id for b in o.bullets] for o in _owners(original)}

    def bullets(owner):
        return [{"id": b.id, "text": b.text, "file_text": original_text.get(b.id), "group": b.group}
                for b in owner.bullets]

    sections = []
    for key in section_order(layout, full):
        if key.startswith("other:"):
            sec = other_section(full, key)
            if sec:
                sections.append({"key": key, "title": sec.heading, "kind": "other",
                                 "lines": [l.text for l in sec.lines]})
            continue
        title = SECTION_TITLES.get(key, key.title())
        if key == "summary" and full.summary:
            sections.append({"key": key, "title": title, "kind": "text", "lines": [full.summary]})
        elif key == "experience" and full.experience:
            sections.append({"key": key, "title": title, "kind": "entries", "entries": [{
                "id": e.id,
                "title": (e.all_roles()[0].title if e.all_roles() else "") or e.company,
                "subtitle": " · ".join(v for v in (e.company, e.location, date_range(e.start_date, e.end_date)) if v),
                "bullets": bullets(e)} for e in full.experience]})
        elif key == "projects" and full.projects:
            sections.append({"key": key, "title": title, "kind": "entries", "entries": [
                {"id": p.id, "title": p.name, "subtitle": "", "bullets": bullets(p)} for p in full.projects]})
        elif key == "education" and full.education:
            sections.append({"key": key, "title": title, "kind": "entries", "entries": [{
                "id": e.id, "title": e.degree or e.institution,
                "subtitle": " · ".join(v for v in (e.institution if e.degree else "", format_date_text(e.dates)) if v),
                "bullets": []} for e in full.education]})
        elif key == "skills" and full.skills:
            sections.append({"key": key, "title": title, "kind": "text",
                             "lines": [f"{c}: {', '.join(v)}" for c, v in display_skills(full.skills).items()]})
        elif key == "certifications" and full.certifications:
            sections.append({"key": key, "title": title, "kind": "text",
                             "lines": [" — ".join(v for k, v in c.items() if v and k != "kind") for c in full.certifications]})
        elif key in ("achievements", "interests") and getattr(full, key):
            sections.append({"key": key, "title": title, "kind": "text", "lines": list(getattr(full, key))})
    return {
        "sections": sections,
        "layout": layout.model_dump(),
        # The layout tailoring produced, for "Reset to the tailored version".
        "default_layout": (default or layout).model_dump(),
        "source_order": {"bullets": source_order,
                         "experience": [e.id for e in original.experience if e.id in {x.id for x in full.experience}],
                         "projects": [p.id for p in original.projects if p.id in {x.id for x in full.projects}],
                         "education": [e.id for e in original.education if e.id in {x.id for x in full.education}]},
        "trimmed": trimmed,
    }


def trimmed_items(before: Resume, after: Resume) -> List[Dict]:
    """What page-fit removed: bullets (with their job), projects, Interests."""
    out: List[Dict] = []
    kept = {b.id for o in _owners(after) for b in o.bullets}
    kept_projects = {p.id for p in after.projects}
    for o in _owners(before):
        if o.id in {p.id for p in before.projects} and o.id not in kept_projects:
            out.append({"kind": "project", "id": o.id, "owner": o.id, "text": o.name})
            continue
        label = getattr(o, "company", None) or getattr(o, "name", "") or o.id
        for b in o.bullets:
            if b.id not in kept:
                out.append({"kind": "bullet", "id": b.id, "owner": o.id, "owner_label": label, "text": b.text})
    if before.interests and not after.interests:
        out.append({"kind": "interests", "id": "interests", "owner": None, "text": ", ".join(before.interests)})
    return out

"""Page-fit loop (P2.4): render, count pages, trim, render again.

The target comes from years of experience (P2.3). When the rendered PDF is
longer, content is removed in a fixed order, least important first:

1. the Interests section;
2. the least JD-relevant bullets (planner flags first, older roles before
   the current one), keeping at least 3 bullets on each current role and 2
   on every other role or project (a sub-heading whose only bullet goes
   is removed with it);
3. the least relevant sub-section of a job, or project, as a whole (the
   job keeps its minimum);
4. compact spacing.

Each render costs a LibreOffice conversion, so the overflow is measured on
the PDF and enough trims to cover it are applied before rendering again, at
most MAX_RENDERS times. Nothing is ever reworded here, only removed, and
every removal is reported.
"""
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from app.analysis.experience import is_ongoing
from app.domain.resume import Resume
from app.domain.resume_document import ResumeDocument

MAX_RENDERS = 4
MIN_BULLETS_CURRENT_ROLE = 3
MIN_BULLETS_OTHER = 2

# Layout estimates for the ATS template (A4, Arial 10.5pt, 0.7" side and
# 0.6" top/bottom margins). Only used to decide how much to trim before the
# next render; the render itself is the judge.
PAGE_BODY_PT = 841.9 - 2 * 0.6 * 72
LINE_PT = 13.4
BULLET_CHARS_PER_LINE = 92
BULLET_GAP_PT = 1.0
HEADING_PT = 26.0
SUBHEADING_PT = 17.0


@dataclass
class FitResult:
    pdf_path: Optional[str]
    pages: Optional[int]
    target_pages: int
    renders: int
    notes: List[str] = field(default_factory=list)

    @property
    def trimmed(self) -> bool:
        return bool(self.notes)

    @property
    def fits(self) -> bool:
        return self.pages is not None and self.pages <= self.target_pages


def measure_pdf(pdf_path: str) -> Tuple[int, float]:
    """(page count, points of the last page used by text below its top margin)."""
    import pymupdf
    with pymupdf.open(pdf_path) as pdf:
        pages = pdf.page_count
        blocks = [b for b in pdf[-1].get_text("blocks") if b[4].strip()]
        top = 0.6 * 72
        used = max((b[3] for b in blocks), default=top) - top
    return pages, max(0.0, used)


def bullet_height(text: str) -> float:
    return max(1, math.ceil(len(text or "") / BULLET_CHARS_PER_LINE)) * LINE_PT + BULLET_GAP_PT


class PageFitter:
    """`render(document, docx_path, out_dir)` writes the DOCX and returns the
    PDF path (None when there is no PDF converter). `measure(pdf_path)`
    returns (pages, points used on the last page)."""

    def __init__(self, render: Callable[[ResumeDocument, str, str], Optional[str]],
                 measure: Callable[[str], Tuple[int, float]] = measure_pdf):
        self.render = render
        self.measure = measure

    def fit(self, document: ResumeDocument, docx_path: str, out_dir: str, target_pages: int,
            relevance: Dict[str, float], trim_candidates: Optional[set] = None,
            pinned: Optional[set] = None, trim: bool = True) -> FitResult:
        """`pinned`: bullet ids, project ids and "interests" the user kept on
        purpose (P8.16); they are never trimmed. `trim=False` ("don't trim")
        renders once and reports the length."""
        resume = document.resume
        trim_candidates = trim_candidates or set()
        pinned = pinned or set()
        steps = [
            lambda need: self._drop_interests(resume) if "interests" not in pinned else (0.0, []),
            lambda need: self._trim_bullets(resume, need, relevance, trim_candidates, pinned),
            lambda need: self._drop_sections(resume, need, relevance, pinned),
            lambda need: self._compact(document),
        ] if trim else []
        result = FitResult(pdf_path=None, pages=None, target_pages=target_pages, renders=0)
        step = 0
        while True:
            result.pdf_path = self.render(document, docx_path, out_dir)
            result.renders += 1
            if not result.pdf_path:
                result.notes.append("Page length not checked: no PDF converter (LibreOffice) available.")
                return result
            pages, last_used = self.measure(result.pdf_path)
            result.pages = pages
            if pages <= target_pages or result.renders >= MAX_RENDERS or step >= len(steps):
                break
            need = max(LINE_PT, (pages - target_pages - 1) * PAGE_BODY_PT + last_used)
            saved = 0.0
            while step < len(steps) and saved < need:
                gained, notes = steps[step](need - saved)
                saved += gained
                result.notes.extend(notes)
                # A step that couldn't save enough is finished; one that met
                # the need may be able to give more next round.
                if saved < need or not notes:
                    step += 1
            if saved == 0.0:
                break  # every step is used up
        if not result.fits and trim:
            result.notes.append(
                f"Still {result.pages} pages after trimming (target {target_pages}); "
                "you can remove or shorten content in Arrange, or choose a longer page target.")
        return result

    # -- trim steps: each returns (estimated points saved, notes) ------------

    @staticmethod
    def _drop_interests(resume: Resume):
        if not resume.interests:
            return 0.0, []
        resume.interests = []
        return HEADING_PT + LINE_PT, ["Removed the Interests section to fit the page target."]

    @staticmethod
    def _trim_bullets(resume: Resume, need: float, relevance: Dict[str, float], trim_candidates: set,
                      pinned: Optional[set] = None):
        """Least relevant bullets first, within the per-role minimums; never
        a pinned one."""
        pinned = pinned or set()
        owners = []  # (section, minimum bullets, is current role)
        for i, exp in enumerate(resume.experience):
            current = _is_current(exp, i)
            owners.append((exp, MIN_BULLETS_CURRENT_ROLE if current else MIN_BULLETS_OTHER, current))
        for project in resume.projects:
            owners.append((project, MIN_BULLETS_OTHER, False))
        candidates = []
        for section, _minimum, current in owners:
            for bullet in section.bullets:
                if bullet.id in pinned:
                    continue
                candidates.append((bullet.id not in trim_candidates, current, relevance.get(bullet.id, 0.0),
                                   section, bullet))
        candidates.sort(key=lambda c: c[:3])
        minimum = {id(s): m for s, m, _ in owners}
        saved, notes = 0.0, []
        for *_key, section, bullet in candidates:
            if saved >= need:
                break
            if len(section.bullets) <= minimum[id(section)]:
                continue
            group = getattr(bullet, "group", None)
            # The last bullet under a sub-heading takes the heading with it.
            alone = bool(group) and sum(1 for b in section.bullets if b.group == group) == 1
            section.bullets.remove(bullet)
            saved += bullet_height(bullet.text) + (SUBHEADING_PT if alone else 0.0)
            notes.append(f"Removed a less relevant bullet from {_owner_label(section)} to fit the page: "
                         f"\"{_short(bullet.text)}\"")
        return saved, notes

    @staticmethod
    def _drop_sections(resume: Resume, need: float, relevance: Dict[str, float], pinned: Optional[set] = None):
        """Least relevant job sub-section or project, as a whole; never one
        holding a pinned bullet, nor a pinned project."""
        pinned = pinned or set()
        options = []  # (mean relevance, height, label, remove)
        for i, exp in enumerate(resume.experience):
            minimum = MIN_BULLETS_CURRENT_ROLE if _is_current(exp, i) else MIN_BULLETS_OTHER
            for group, bullets in exp.bullet_groups():
                if not group or len(exp.bullets) - len(bullets) < minimum:
                    continue
                ids = {b.id for b in bullets}
                if ids & pinned:
                    continue
                options.append((
                    sum(relevance.get(b.id, 0.0) for b in bullets) / len(bullets),
                    SUBHEADING_PT + sum(bullet_height(b.text) for b in bullets),
                    f"the \"{group}\" sub-section of {_owner_label(exp)}",
                    lambda exp=exp, ids=ids: setattr(exp, "bullets", [b for b in exp.bullets if b.id not in ids]),
                ))
        for project in resume.projects:
            if project.id in pinned or {b.id for b in project.bullets} & pinned:
                continue
            mean = (sum(relevance.get(b.id, 0.0) for b in project.bullets) / len(project.bullets)
                    if project.bullets else 0.0)
            options.append((
                mean,
                SUBHEADING_PT + sum(bullet_height(b.text) for b in project.bullets),
                f"the \"{project.name}\" project",
                lambda project=project: resume.projects.remove(project),
            ))
        saved, notes = 0.0, []
        for _mean, height, label, remove in sorted(options, key=lambda o: o[0]):
            if saved >= need:
                break
            remove()
            saved += height
            notes.append(f"Removed {label} (least relevant to the JD) to fit the page.")
        return saved, notes

    @staticmethod
    def _compact(document: ResumeDocument):
        if document.presentation.compact:
            return 0.0, []
        document.presentation.compact = True
        return 3 * LINE_PT, ["Used compact spacing to fit the page."]


def _is_current(exp, index: int) -> bool:
    """The first job, and any other job that hasn't ended, keep the larger
    bullet minimum."""
    roles = exp.all_roles()
    return index == 0 or bool(roles and is_ongoing(roles[0].end_date))


def _owner_label(section) -> str:
    """"Lakeshore Electric (Journeyman Electrician)" or a project's name, so
    a trim note says where it came from (P8.16)."""
    if hasattr(section, "company"):
        roles = section.all_roles()
        title = roles[0].title if roles else ""
        name = section.company or title or "a job"
        return f"{name} ({title})" if section.company and title else name
    return f"the \"{section.name}\" project"


def _short(text: str, limit: int = 70) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"

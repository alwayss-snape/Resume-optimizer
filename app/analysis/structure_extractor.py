"""LLM-assisted resume structure extraction with a verbatim guard (P1.13).

The deterministic parser (ingestion + ResumeNormalizer) handles the layouts
it knows. When its result looks wrong (no name, a job without a company or
title, a job with no bullets, text outside any known section), this module
asks the LLM to *label* the numbered lines of the file: which line is the
name, a section heading, a company, a job title, a sub-heading, a bullet.
It never asks for text. The labels become `hint`s on the raw blocks and
the normalizer runs again, so every value in the result is still copied
verbatim from the file. The same pattern as JD line selection.
"""
import logging
import re
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from app.analysis.resume_normalizer import ResumeNormalizer
from app.domain.evidence import Evidence
from app.domain.resume import Resume
from app.domain.resume_document import ResumeDocument
from app.ingestion.docx import RawDocument
from app.llm.client import LLMClient

logger = logging.getLogger(__name__)

LineLabelName = Literal[
    "name", "headline", "contact",
    "section_summary", "section_experience", "section_projects", "section_skills",
    "section_education", "section_certifications", "section_interests", "section_awards", "section_other",
    "company", "job_title", "subheading", "bullet", "text",
]

# A section label maps to a canonical heading the normalizer recognises.
_SECTION_HEADINGS = {
    "section_summary": "Summary", "section_experience": "Experience", "section_projects": "Projects",
    "section_skills": "Skills", "section_education": "Education",
    "section_certifications": "Certifications", "section_interests": "Interests",
    "section_awards": "Awards", "section_other": "Other",
}


class LineLabel(BaseModel):
    index: int
    label: LineLabelName


class ResumeLineLabels(BaseModel):
    """Structural role of each numbered resume line, selected by INDEX. The
    caller copies all text from its own lines, so nothing can be invented."""
    lines: List[LineLabel] = Field(default_factory=list)


_SYSTEM_PROMPT = """You label the lines of a resume by their structural role.

Each line is numbered. For every line, return its index and one label:
- name: the candidate's full name
- headline: a short professional title under the name (e.g. "Senior Data Scientist")
- contact: email, phone, location, links
- section_summary / section_experience / section_projects / section_skills / section_education /
  section_certifications / section_interests / section_awards / section_other: a section heading
- company: an employer name line (may include a location)
- job_title: a job title line, usually with dates
- subheading: a heading inside a job, such as a project or client name
- bullet: an achievement or responsibility line
- text: any other content (summary sentences, skills lists, education lines, certification items)

Return only indices and labels, exactly as numbered. Never rewrite or invent text."""


class StructureExtractor:
    # A job line has a year or "Present"; mirrors ResumeNormalizer.
    _YEAR_OR_PRESENT = ResumeNormalizer.YEAR_OR_PRESENT
    MAX_LINES = 250

    def __init__(self, llm_client: Optional[LLMClient] = None, normalizer: Optional[ResumeNormalizer] = None):
        self.llm_client = llm_client
        self.normalizer = normalizer or ResumeNormalizer()

    # -- deciding whether to ask --------------------------------------

    def problems(self, resume: Resume, evidence: List[Evidence], raw_doc: RawDocument) -> List[str]:
        """Signs that the deterministic parse misread the layout."""
        issues: List[str] = []
        name = (resume.candidate.name or "").strip()
        if not name or name == "Candidate":
            issues.append("no candidate name")
        elif "@" in name or re.search(r"\d", name) or self.normalizer.SECTION_KEYWORDS_RE.search(name):
            issues.append(f"name looks wrong: {name!r}")
        has_bullets = any(b.block_type == "bullet" for b in raw_doc.blocks)
        if has_bullets and not resume.experience and not resume.projects:
            issues.append("bullets found but no experience or projects")
        for exp in resume.experience:
            label = exp.company or exp.title or exp.id
            if not exp.company:
                issues.append(f"experience without a company ({label})")
            if not exp.title:
                issues.append(f"experience without a title ({label})")
            if not exp.bullets:
                issues.append(f"experience without bullets ({label})")
        stray = [e for e in evidence if e.source_type == "general"]
        if len(stray) >= 3:
            issues.append(f"{len(stray)} lines outside any known section")
        return issues

    # -- asking ---------------------------------------------------------

    def label_lines(self, raw_doc: RawDocument) -> Optional[List[Tuple[int, str]]]:
        """Ask the LLM for a label per block index. None if unavailable or
        the answer is unusable."""
        if not self.llm_client or not self.llm_client.is_available():
            return None
        blocks = raw_doc.blocks[: self.MAX_LINES]
        numbered = "\n".join(f"{i}: {b.text[:160]}" for i, b in enumerate(blocks))
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Numbered resume lines:\n{numbered}"},
        ]
        try:
            result = self.llm_client.generate_json(
                messages=messages, schema_model=ResumeLineLabels, temperature=0.0, effort="low",
            )
        except Exception as e:  # the deterministic parse stands
            logger.warning("Structure extraction call failed: %s", e)
            return None
        # Drop indices we never sent (hallucinated) and duplicates.
        seen = set()
        labels = []
        for item in result.lines:
            if 0 <= item.index < len(blocks) and item.index not in seen:
                seen.add(item.index)
                labels.append((item.index, item.label))
        if len(labels) < max(3, len(blocks) // 2):
            return None
        return labels

    @staticmethod
    def apply_labels(raw_doc: RawDocument, labels: List[Tuple[int, str]]) -> RawDocument:
        """A copy of raw_doc with each labelled block carrying a hint. Text
        is untouched; section labels become canonical heading hints."""
        doc = raw_doc.model_copy(deep=True)
        for index, label in labels:
            block = doc.blocks[index]
            if label in _SECTION_HEADINGS:
                block.hint = f"section:{_SECTION_HEADINGS[label]}"
            elif label in ("name", "company", "job_title", "subheading", "bullet"):
                block.hint = label
        return doc

    # -- the whole step -------------------------------------------------

    def improve(
        self, raw_doc: RawDocument, resume_doc: ResumeDocument, evidence: List[Evidence],
    ) -> Tuple[ResumeDocument, List[Evidence], List[str]]:
        """Return the better of the deterministic parse and an LLM-guided
        re-parse, plus the problems that remain in the one returned."""
        issues = self.problems(resume_doc.resume, evidence, raw_doc)
        if not issues:
            return resume_doc, evidence, []
        labels = self.label_lines(raw_doc)
        if labels is None:
            return resume_doc, evidence, issues
        hinted = self.apply_labels(raw_doc, labels)
        new_doc, new_evidence = self.normalizer.normalize(hinted)
        new_issues = self.problems(new_doc.resume, new_evidence, hinted)
        if len(new_issues) < len(issues):
            logger.info("Structure extraction fixed: %s", sorted(set(issues) - set(new_issues)))
            new_doc.record_revision(
                "Structure re-read with LLM line labels (text copied verbatim)",
                ["resume"], actor="import",
            )
            return new_doc, new_evidence, new_issues
        return resume_doc, evidence, issues

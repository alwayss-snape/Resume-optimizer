"""Canonical projection of a parsed resume, compared against hand-checked
golden files (tests/integration/test_parse_golden.py and the harness)."""
from typing import Dict, List

from app.analysis.resume_normalizer import ResumeNormalizer
from app.domain.resume import Resume
from app.ingestion.docx import DocxParser
from app.ingestion.pdf import PdfParser


def project_resume(resume: Resume) -> Dict:
    """The parts of a parsed resume a golden file pins down."""
    c = resume.candidate
    return {
        "candidate": {
            "name": c.name, "headline": c.headline, "email": c.email,
            "phone": c.phone, "location": c.location, "links": list(c.links),
        },
        "summary": resume.summary,
        "experience": [
            {
                "company": e.company,
                "location": e.location,
                "roles": [[r.title, r.start_date, r.end_date] for r in e.all_roles()],
                "groups": [[g, [b.text for b in bullets]] for g, bullets in e.bullet_groups()],
            }
            for e in resume.experience
        ],
        "projects": [{"name": p.name, "bullets": [b.text for b in p.bullets]} for p in resume.projects],
        "skills": resume.skills,
        "education": [
            {"institution": e.institution, "degree": e.degree, "location": e.location, "dates": e.dates}
            for e in resume.education
        ],
        "certifications": [c.get("name") for c in resume.certifications],
        "achievements": resume.achievements,
        "interests": resume.interests,
    }


def project(resume_path: str) -> Dict:
    """Parse a file deterministically (no LLM) and project it."""
    parser = PdfParser() if resume_path.lower().endswith(".pdf") else DocxParser()
    return project_resume(ResumeNormalizer().normalize(parser.parse(resume_path))[0].resume)


def golden_mismatches(parsed: Dict, golden: Dict) -> List[str]:
    """Top-level fields where the parse differs from the golden file."""
    return [key for key in golden if parsed.get(key) != golden[key]]

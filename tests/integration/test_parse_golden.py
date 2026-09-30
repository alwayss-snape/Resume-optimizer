"""Parse a resume and compare it, field by field, with a hand-checked golden
file (Stage A exit gate).

The replica case is committed. The real-resume case runs only on a machine
that has the private files in data/eval/private/ (gitignored), so it's
skipped in CI and on fresh clones.

To create or refresh a golden file after checking the parse by eye:
    python tests/integration/test_parse_golden.py <resume.pdf|docx> > <golden.json>
"""
import json
import os
import sys

import pytest

from app.analysis.resume_normalizer import ResumeNormalizer
from app.ingestion.docx import DocxParser
from app.ingestion.pdf import PdfParser

CASES = [
    ("tests/fixtures/resumes/replica_layout.pdf", "tests/fixtures/resumes/replica_layout.golden.json"),
    ("data/eval/private/resume.pdf", "data/eval/private/resume.golden.json"),
]


def project(resume_path: str) -> dict:
    """The parts of a parsed resume a golden file pins down."""
    parser = PdfParser() if resume_path.lower().endswith(".pdf") else DocxParser()
    resume = ResumeNormalizer().normalize(parser.parse(resume_path))[0].resume
    c = resume.candidate
    return {
        "candidate": {
            "name": c.name, "headline": getattr(c, "headline", None), "email": c.email,
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


@pytest.mark.parametrize("resume_path,golden_path", CASES, ids=["replica", "private-real-resume"])
def test_parse_matches_golden(resume_path, golden_path):
    if not (os.path.exists(resume_path) and os.path.exists(golden_path)):
        pytest.skip(f"{resume_path} / {golden_path} not present")
    with open(golden_path, encoding="utf-8") as f:
        golden = json.load(f)
    parsed = project(resume_path)
    for key in golden:
        assert parsed[key] == golden[key], f"{key} differs from {golden_path}"


if __name__ == "__main__":
    print(json.dumps(project(sys.argv[1]), indent=2, ensure_ascii=False))

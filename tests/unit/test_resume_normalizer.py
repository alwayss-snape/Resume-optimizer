import pytest
from app.analysis.resume_normalizer import ResumeNormalizer
from app.domain.evidence import Evidence
from app.domain.resume import Resume
from app.ingestion.docx import DocxParser

def test_resume_normalizer():
    sample_path = "tests/fixtures/resumes/sample.docx"
    parser = DocxParser()
    raw_doc = parser.parse(sample_path)

    normalizer = ResumeNormalizer()
    resume_doc, evidence_list = normalizer.normalize(raw_doc)

    assert hasattr(resume_doc, "resume")
    resume = resume_doc.resume
    assert isinstance(resume, Resume)
    assert resume.candidate.name == "Jane Doe"
    assert resume.candidate.email == "jane.doe@example.com"
    assert resume.summary is not None
    assert "6+ years" in resume.summary

    assert len(resume.experience) >= 2
    assert resume.experience[0].company.startswith("Acme")
    assert len(resume.experience[0].bullets) >= 3

    assert "Languages" in resume.skills
    assert "Python" in resume.skills["Languages"]

    assert len(evidence_list) > 0
    first_ev = evidence_list[0]
    assert isinstance(first_ev, Evidence)
    assert first_ev.id.startswith("ev_")

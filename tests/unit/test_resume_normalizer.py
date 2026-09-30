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


def _normalize_replica():
    from app.ingestion.pdf import PdfParser
    raw = PdfParser().parse("tests/fixtures/resumes/replica_layout.pdf")
    resume_doc, evidence = ResumeNormalizer().normalize(raw)
    return resume_doc.resume, evidence


def test_replica_header_summary_and_contact():
    resume, _ = _normalize_replica()
    assert resume.candidate.name == "Jordan Avery"
    assert resume.candidate.email == "jordan.avery@example.com"
    assert resume.candidate.phone == "+91-9000000000"
    assert resume.candidate.location == "Pune, India"
    assert resume.summary.startswith("Data Scientist with 4 years")
    assert resume.summary.endswith("measurable business outcomes.")


def test_replica_multi_category_skill_line_split():
    resume, _ = _normalize_replica()
    assert resume.skills == {
        "Languages": ["Python", "Scala", "SQL", "R"],
        "Frameworks": ["Pandas", "NumPy", "PyTorch", "XGBoost"],
        "Tools": ["PostgreSQL", "Tableau", "Airflow", "GCP", "Excel"],
    }


def test_replica_education_right_columns():
    resume, _ = _normalize_replica()
    [edu] = resume.education
    assert edu.institution == "Riverside Institute of Technology"
    assert edu.location == "Chennai, India"
    assert edu.degree == "B.Tech in Electronics Engineering(CGPA : 8.5/10)"
    assert edu.dates == "2016-2020"


def test_replica_labelled_certifications_not_filed_as_interests():
    resume, evidence = _normalize_replica()
    assert [c["name"] for c in resume.certifications] == [
        "Google Cloud Professional Data Engineer", "Statistics for Data Science",
    ]
    assert resume.interests == ["Chess", "Cycling", "Photography"]
    assert any(e.source_type == "certification" for e in evidence)


def test_split_skill_line_single_space_before_label():
    n = ResumeNormalizer()
    assert n._split_skill_line("Languages: Python, SQL Frameworks: Pandas, and XGBoost") == [
        ("Languages", ["Python", "SQL"]), ("Frameworks", ["Pandas", "XGBoost"]),
    ]
    assert n._split_skill_line("Python, Java") == [("Skills", ["Python", "Java"])]

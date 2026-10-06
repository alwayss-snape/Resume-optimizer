"""P10.1: a LinkedIn "Save to PDF" export is read by its own two-column
layout; anything else, or an export that doesn't read cleanly, takes the
normal PDF path. The full parse is pinned by
tests/fixtures/resumes/linkedin_export.golden.json (test_parse_golden.py)."""
import pymupdf as fitz

from app.analysis.resume_normalizer import ResumeNormalizer
from app.ingestion.linkedin import LAYOUT, NOTE
from app.ingestion.pdf import PdfParser
from app.services.tailor import TailorService

EXPORT = "tests/fixtures/resumes/linkedin_export.pdf"
REPLICA = "tests/fixtures/resumes/replica_layout.pdf"
JD = "tests/fixtures/jds/sample.txt"
GREY = (0.45, 0.45, 0.45)


def _pdf(path, lines):
    """lines: (x, y, text, size, colour); Helvetica, one Letter page."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for x, y, text, size, color in lines:
        page.insert_text((x, y), text, fontsize=size, fontname="helv", color=color)
    doc.save(str(path))
    return str(path)


def _export_lines(dates_color=GREY, description_first=False):
    """A minimal export: sidebar Contact, then name, headline, place and one job."""
    lines = [
        (28, 62, "Contact", 13, (0, 0, 0)),
        (28, 82, "sam.lee@example.com", 10.5, (0, 0, 0)),
        (28, 96, "www.linkedin.com/in/sam-lee-01 (LinkedIn)", 7, (0, 0, 0)),
        (220, 80, "Sam Lee", 26, (0, 0, 0)),
        (220, 100, "Data Analyst", 12, (0, 0, 0)),
        (220, 116, "Pune, Maharashtra, India", 10.5, GREY),
        (220, 150, "Experience", 15.75, (0, 0, 0)),
    ]
    body = [
        (220, 170, "Acme Retail", 12, (0, 0, 0)),
        (220, 186, "Data Analyst", 11.5, (0, 0, 0)),
        (220, 200, "May 2021 - Present (3 years)", 10.5, dates_color),
        (220, 214, "Pune, Maharashtra, India", 10.5, dates_color),
        (220, 230, "Built weekly sales dashboards in Tableau for 40 stores.", 10.5, (0, 0, 0)),
    ]
    if description_first:
        body.insert(0, (220, 166, "Analysed store sales before joining the team.", 10.5, (0, 0, 0)))
    return lines + body + [(283, 770, "Page 1 of 1", 9, GREY)]


def test_the_export_is_read_by_its_layout():
    raw = PdfParser().parse(EXPORT)
    assert raw.layout == LAYOUT
    # Page footers and LinkedIn's durations are not content.
    assert "Page 1 of 2" not in raw.raw_text and "4 years 10 months" not in raw.raw_text
    assert "(2 years 7 months)" not in raw.raw_text
    resume = ResumeNormalizer().normalize(raw)[0].resume
    # A sidebar section with no home of its own is kept verbatim.
    assert [(s.heading, [l.text for l in s.lines]) for s in resume.other_sections] == [
        ("Languages", ["English (Full Professional)", "Hindi (Native or Bilingual)"])]


def test_other_pdfs_take_the_normal_path():
    assert PdfParser().parse(REPLICA).layout is None


def test_a_one_column_resume_with_a_contact_heading_and_a_profile_url_is_not_an_export(tmp_path):
    path = _pdf(tmp_path / "one_column.pdf", [
        (40, 60, "Sam Lee", 24, (0, 0, 0)),
        (40, 90, "Contact", 13, (0, 0, 0)),
        (40, 106, "sam.lee@example.com | www.linkedin.com/in/sam-lee-01", 10.5, (0, 0, 0)),
        (40, 130, "Experience", 13, (0, 0, 0)),
        (40, 146, "Data Analyst, Acme Retail, May 2021 - Present", 10.5, (0, 0, 0)),
        (283, 770, "Page 1 of 1", 9, GREY),
    ])
    assert PdfParser().parse(path).layout is None


def test_an_export_that_does_not_read_cleanly_falls_back(tmp_path):
    # A description before any role: not the pattern, so the normal parse runs.
    path = _pdf(tmp_path / "odd.pdf", _export_lines(description_first=True))
    raw = PdfParser().parse(path)
    assert raw.layout is None
    assert "Analysed store sales before joining the team." in raw.raw_text


def test_a_role_location_is_found_without_grey_text(tmp_path):
    # Some viewers print the export in black only: the place is found by its shape.
    path = _pdf(tmp_path / "black.pdf", _export_lines(dates_color=(0, 0, 0)))
    raw = PdfParser().parse(path)
    assert raw.layout == LAYOUT
    resume = ResumeNormalizer().normalize(raw)[0].resume
    job = resume.experience[0]
    assert (job.company, job.location, job.title, job.start_date, job.end_date) == (
        "Acme Retail", "Pune, Maharashtra, India", "Data Analyst", "May 2021", "Present")
    assert [b.text for b in job.bullets] == ["Built weekly sales dashboards in Tableau for 40 stores."]
    assert resume.candidate.location == "Pune, Maharashtra, India"
    assert resume.candidate.links == ["www.linkedin.com/in/sam-lee-01"]


class _CountingLLM:
    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def generate_json(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("the LinkedIn layout needs no LLM re-label")


def test_no_llm_relabel_for_an_export():
    llm = _CountingLLM()
    service = TailorService(llm_client=llm)
    _, resume_doc, _ = service.parse_resume(EXPORT)
    assert llm.calls == 0
    # P10.11: a role with no description is normal in an export, so it is not
    # a reading problem; how the file was read is a note, not an issue.
    assert service.last_parse_issues == []
    assert service.last_parse_notes == [NOTE]
    assert resume_doc.resume.experience[-1].company == "Northstar Labs"


def test_an_export_tailors_offline_with_nothing_lost(tmp_path):
    service = TailorService(llm_client=None)
    with open(JD, encoding="utf-8") as f:
        jd = f.read()
    result = service.tailor_resume(EXPORT, jd, str(tmp_path), preapproved_proposals=[],
                                   parsed=service.parse_resume(EXPORT), remember_answers=False)
    assert result["coverage"]["lost"] == [] and result["coverage"]["pct"] == 100.0
    assert result["success"] is True


def test_the_api_returns_the_note_apart_from_the_issues_p1011():
    from fastapi.testclient import TestClient
    from app.api.main import create_app
    client = TestClient(create_app(make_service=lambda model=None: TailorService(llm_client=None, keep_run=False)))
    with open(EXPORT, "rb") as f, open(JD, encoding="utf-8") as jd:
        body = client.post("/api/parse", files={"file": ("Profile.pdf", f, "application/pdf")},
                           data={"jd_text": jd.read()}).json()
    assert body["parse_notes"] == [NOTE] and body["parse_issues"] == []
    assert body["details"]["candidate"]["location"] == "Bengaluru, Karnataka, India"

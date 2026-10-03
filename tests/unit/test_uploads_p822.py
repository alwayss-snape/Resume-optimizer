"""P8.22: every upload gets a result or a message the person can act on."""
import pymupdf
import pytest

from app.eval.harness import OfflineLLM
from app.ingestion import errors
from app.ingestion.errors import UnreadableFile
from app.services.tailor import TailorService

UT = "docs/user_testing/2026-10-02/resumes/"


def _service():
    return TailorService(llm_client=OfflineLLM())


@pytest.mark.parametrize("name, message", [
    ("corrupt.docx", errors.DAMAGED_DOCX), ("encrypted.pdf", errors.LOCKED_PDF), ("empty.docx", errors.NO_TEXT),
])
def test_broken_files_get_specific_messages(name, message):
    with pytest.raises(UnreadableFile) as e:
        _service().parse_resume(UT + name)
    assert str(e.value) == message


def test_scanned_pdf_is_explained(tmp_path):
    img = pymupdf.open()
    page = img.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 100), False)
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(50, 50, 450, 250), pixmap=pix)
    path = str(tmp_path / "scan.pdf")
    img.save(path)
    with pytest.raises(UnreadableFile) as e:
        _service().parse_resume(path)
    assert str(e.value) == errors.SCANNED_PDF


def test_plain_text_resume_is_read(tmp_path):
    path = tmp_path / "r.txt"
    path.write_text("Jane Doe\njane@example.com | 512-555-0199\n\nEXPERIENCE\nData Analyst | Acme | Jan 2020 - Present\n"
                    "- Built SQL dashboards for 3 teams\n\nEDUCATION\nB.S. Statistics, State University, 2019\n")
    resume = _service().parse_resume(str(path))[1].resume
    assert resume.candidate.name == "Jane Doe" and resume.candidate.phone == "512-555-0199"
    assert [(e.company, e.title, len(e.bullets)) for e in resume.experience] == [("Acme", "Data Analyst", 1)]
    assert len(resume.education) == 1

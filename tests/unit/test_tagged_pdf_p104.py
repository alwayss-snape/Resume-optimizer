"""P10.4: the PDF is tagged (accessible), and tagging changes nothing a
reader or the round-trip sees."""
import os
import shutil

import pymupdf
import pytest

from app.rendering import pdf_converter
from app.rendering.pdf_converter import PdfConverter, _enable_tagged_pdf

SAMPLE = "tests/fixtures/resumes/sample.docx"


def test_the_setting_is_added_once_and_keeps_existing_settings(tmp_path):
    _enable_tagged_pdf(str(tmp_path))
    path = tmp_path / "user" / "registrymodifications.xcu"
    first = path.read_text()
    assert first.count("UseTaggedPDF") == 1 and first.rstrip().endswith("</oor:items>")
    _enable_tagged_pdf(str(tmp_path))
    assert path.read_text() == first
    other = tmp_path / "other"
    (other / "user").mkdir(parents=True)
    (other / "user" / "registrymodifications.xcu").write_text(
        first.replace(pdf_converter._TAGGED_PDF_ITEM, '<item oor:path="/x"><prop oor:name="Y"><value>1</value></prop></item>'))
    _enable_tagged_pdf(str(other))
    text = (other / "user" / "registrymodifications.xcu").read_text()
    assert 'oor:path="/x"' in text and "UseTaggedPDF" in text


@pytest.mark.skipif(not PdfConverter().find_libreoffice_binary(), reason="needs LibreOffice")
def test_pdf_is_tagged_with_the_same_pages_and_text(tmp_path, monkeypatch):
    tagged = PdfConverter().convert_docx_to_pdf(SAMPLE, str(tmp_path / "tagged"))
    # The same file through a profile without the setting.
    monkeypatch.setattr(pdf_converter, "_free_profiles", [])
    monkeypatch.setattr(pdf_converter, "_enable_tagged_pdf", lambda profile: None)
    monkeypatch.setattr(pdf_converter, "_PROFILE_ROOT", str(tmp_path / "plain_profiles"))
    plain = PdfConverter().convert_docx_to_pdf(SAMPLE, str(tmp_path / "plain"))
    with pymupdf.open(tagged) as t, pymupdf.open(plain) as p:
        assert t.xref_get_key(t.pdf_catalog(), "MarkInfo") == ("dict", "<</Marked true>>")
        assert t.xref_get_key(t.pdf_catalog(), "StructTreeRoot")[0] == "xref"
        assert p.xref_get_key(p.pdf_catalog(), "StructTreeRoot")[0] == "null"
        assert t.page_count == p.page_count
        assert [pg.get_text() for pg in t] == [pg.get_text() for pg in p]

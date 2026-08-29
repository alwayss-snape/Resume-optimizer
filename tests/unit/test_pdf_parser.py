import os
import pytest
from app.ingestion.pdf import PdfParser
from app.ingestion.docx import RawDocument

def test_pdf_parser_text_layer():
    sample_path = "tests/fixtures/resumes/sample.pdf"
    assert os.path.exists(sample_path)

    parser = PdfParser()
    raw_doc = parser.parse(sample_path)

    assert isinstance(raw_doc, RawDocument)
    assert raw_doc.filename == "sample.pdf"
    assert len(raw_doc.blocks) > 0

    # Check text content extracted
    text_content = raw_doc.raw_text
    assert "Jane Doe" in text_content
    assert "Python" in text_content

def test_pdf_parser_file_not_found():
    parser = PdfParser()
    with pytest.raises(FileNotFoundError):
        parser.parse("non_existent_file.pdf")

import os
import pytest
from app.rendering.pdf_converter import PdfConverter
from app.validation.output import OutputQAValidator

def test_pdf_converter_find_binary_or_graceful_none():
    converter = PdfConverter()
    binary = converter.find_libreoffice_binary()
    # On systems where LibreOffice is not installed, binary should be None gracefully
    if binary is not None:
        assert isinstance(binary, str)

def test_output_qa_validator(tmp_path):
    sample_docx = "tests/fixtures/resumes/sample.docx"
    sample_pdf = "tests/fixtures/resumes/sample.pdf"

    validator = OutputQAValidator()
    docx_warnings = validator.validate_docx(sample_docx, expected_candidate_name="Jane Doe")
    assert len(docx_warnings) == 0

    pdf_warnings = validator.validate_pdf(sample_pdf, expected_candidate_name="Jane Doe")
    assert len(pdf_warnings) == 0

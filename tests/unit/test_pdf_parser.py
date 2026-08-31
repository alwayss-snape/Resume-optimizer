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


def test_merge_wrapped_lines_joins_lowercase_continuation():
    """A word-wrapped sentence split across two PDF lines, where the second
    line continues mid-sentence in lowercase, must be joined into one line."""
    parser = PdfParser()
    lines = [
        "Built a Python-based MLOps framework on Azure Databricks and Azure",
        "cloud services, automating data ingestion, model training.",
    ]
    result = parser._merge_wrapped_lines(lines)
    assert result == [
        "Built a Python-based MLOps framework on Azure Databricks and Azure cloud services, automating data ingestion, model training."
    ]


def test_merge_wrapped_lines_does_not_merge_name_and_contact_line():
    """A short name line followed by a capitalized contact-info line must NOT
    be merged — this was the original regression (Jane Doe candidate-name
    detection breaking)."""
    parser = PdfParser()
    lines = ["Jane Doe", "Email: jane.doe@example.com | Phone: 555-0199"]
    result = parser._merge_wrapped_lines(lines)
    assert result == ["Jane Doe", "Email: jane.doe@example.com | Phone: 555-0199"]


def test_merge_wrapped_lines_does_not_merge_headings():
    """A Title-Case section heading followed by its content must stay
    separate, even though the heading isn't ALL-CAPS."""
    parser = PdfParser()
    lines = ["Professional Summary", "Senior Software Engineer with 6+ years of experience."]
    result = parser._merge_wrapped_lines(lines)
    assert result == ["Professional Summary", "Senior Software Engineer with 6+ years of experience."]


def test_merge_wrapped_lines_does_not_merge_across_bullets():
    """A lowercase-starting bullet (unusual but possible) must never be
    merged into the previous bullet — bullet prefixes always start a new line."""
    parser = PdfParser()
    lines = ["Owns the deployment pipeline.", "- built internal tooling for on-call rotations"]
    result = parser._merge_wrapped_lines(lines)
    assert result == ["Owns the deployment pipeline.", "- built internal tooling for on-call rotations"]


def test_pdf_parser_end_to_end_no_truncated_bullets():
    """Regression guard: sample.pdf's known multi-line bullet must come
    through as one complete sentence, not split into fragments."""
    parser = PdfParser()
    raw_doc = parser.parse("tests/fixtures/resumes/sample.pdf")
    texts = [b.text for b in raw_doc.blocks]
    # Name and contact info must remain distinct blocks (regression guard).
    assert "Jane Doe" in texts
    assert not any(t.startswith("Jane Doe Email") for t in texts)

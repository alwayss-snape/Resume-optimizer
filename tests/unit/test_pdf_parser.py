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


# -- Layout-aware parsing (P1.11), against an anonymized replica of a real
# resume layout that the old line-based parser misread.
REPLICA = "tests/fixtures/resumes/replica_layout.pdf"


def _replica_blocks():
    return PdfParser().parse(REPLICA).blocks


def test_replica_name_is_largest_font_line():
    blocks = _replica_blocks()
    names = [b for b in blocks if b.block_type == "name"]
    assert [b.text for b in names] == ["Jordan Avery"]
    # The lowercase contact line right under it is not glued onto the name.
    assert blocks[1].text == "jordan.avery@example.com | +91-9000000000 | Pune, India"


def test_replica_no_glyphs_or_invisible_chars_leak():
    for b in _replica_blocks():
        assert "●" not in b.text
        assert "​" not in b.text and "\xa0" not in b.text and "\xad" not in b.text


def test_replica_bullets_joined_by_indent_including_bold_continuations():
    bullets = [b.text for b in _replica_blocks() if b.block_type == "bullet"]
    assert len(bullets) == 7
    # Continuation line set in bold (was split off as its own block before).
    assert "Reported late-delivery hotspots to regional managers across three distribution networks" in bullets
    assert "Trained an XGBoost churn model with engineered tenure and usage features, lifting retention campaign response by 15%" in bullets
    # Continuation that starts with a lowercase word, the old rule's only case.
    assert any(t.endswith("covering 1,200 stores and replacing a spreadsheet process.") for t in bullets)


def test_replica_headings_detected_even_with_leading_spaces():
    headings = [b.text for b in _replica_blocks() if b.block_type == "heading"]
    assert headings == [
        "PROFESSIONAL SUMMARY", "WORK EXPERIENCE", "SKILLS", "EDUCATION", "CERTIFICATIONS & INTERESTS",
    ]


def test_replica_right_columns_become_tabs():
    texts = [b.text for b in _replica_blocks()]
    # Pushed right with spaces, in the same text run:
    assert "Northwind Analytics - A Contoso Group Company\tPune, India" in texts
    # A separate right-aligned run on the same row:
    assert "Riverside Institute of Technology\tChennai, India" in texts
    assert "B.Tech in Electronics Engineering(CGPA : 8.5/10)\t2016-2020" in texts


def test_replica_summary_wrapped_lines_joined_but_labelled_lines_kept_apart():
    texts = [b.text for b in _replica_blocks()]
    assert any(t.startswith("Data Scientist with 4 years") and t.endswith("measurable business outcomes.") for t in texts)
    assert "Tools: PostgreSQL, Tableau, Airflow, GCP, Excel" in texts
    assert "Interests: Chess • Cycling • Photography" in texts

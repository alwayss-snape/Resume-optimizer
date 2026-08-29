import os
import pytest
from app.ingestion.docx import DocxParser, RawDocument
from app.rendering.document_map import DocumentLocation, DocumentMap

def test_docx_parser_sample():
    sample_path = "tests/fixtures/resumes/sample.docx"
    assert os.path.exists(sample_path)

    parser = DocxParser()
    raw_doc = parser.parse(sample_path)

    assert isinstance(raw_doc, RawDocument)
    assert raw_doc.filename == "sample.docx"
    assert len(raw_doc.blocks) > 0

    # Verify headings detection
    headings = [b for b in raw_doc.blocks if b.block_type == "heading"]
    heading_texts = [h.text for h in headings]
    assert "Professional Summary" in heading_texts
    assert "Work Experience" in heading_texts

    # Verify bullet points detection
    bullets = [b for b in raw_doc.blocks if b.block_type == "bullet"]
    assert len(bullets) >= 5
    first_bullet = bullets[0]
    assert "microservices" in first_bullet.text

    # Verify DocumentMap tracking
    doc_map = raw_doc.document_map
    assert len(doc_map.locations) == len(raw_doc.blocks)
    loc = doc_map.get_location(first_bullet.id)
    assert loc is not None
    assert isinstance(loc, DocumentLocation)
    assert loc.paragraph_index is not None

def test_docx_parser_file_not_found():
    parser = DocxParser()
    with pytest.raises(FileNotFoundError):
        parser.parse("non_existent_file.docx")

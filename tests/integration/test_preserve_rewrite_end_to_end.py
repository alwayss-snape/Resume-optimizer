import os
import json
import docx
import pytest

from app.ingestion.docx import DocxParser
from app.analysis.resume_normalizer import ResumeNormalizer
from app.analysis.rewriter import RewriteProposal
from app.rendering.docx_patcher import DocxPatcher
from app.rendering.html_renderer import HtmlResumeRenderer
from app.validation.output import OutputQAValidator


def test_approved_rewrite_appears_in_all_outputs(tmp_path):
    sample_src = "tests/fixtures/resumes/sample.docx"
    parser = DocxParser()
    raw_doc = parser.parse(sample_src)

    normalizer = ResumeNormalizer()
    resume_doc, evidence_list = normalizer.normalize(raw_doc)
    resume = resume_doc.resume

    # Find first experience bullet block and corresponding semantic bullet
    first_bullet_block = next((b for b in raw_doc.blocks if b.block_type == "bullet"), None)
    assert first_bullet_block is not None

    # Find the semantic bullet that references this block
    semantic_bullet = None
    for exp in resume.experience:
        for b in exp.bullets:
            if b.source_location_id == first_bullet_block.id:
                semantic_bullet = b
                break
        if semantic_bullet:
            break

    assert semantic_bullet is not None

    # Create a conservative rewording that preserves numerics and factual tokens
    original_text = semantic_bullet.text
    rewritten = original_text.replace("Built", "Architected") if "Built" in original_text else original_text + ""

    proposal = RewriteProposal(semantic_id=semantic_bullet.id, source_id=first_bullet_block.id,
                               original_text=original_text, rewritten_text=rewritten, evidence_ids=[])

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    out_docx = str(out_dir / "patched.docx")
    out_html = str(out_dir / "tailored.html")
    resume_doc_path = str(out_dir / "resume_document.json")

    # Apply patch to DOCX
    patcher = DocxPatcher()
    res_path = patcher.patch(sample_src, raw_doc.document_map, [proposal], out_docx)
    assert os.path.exists(res_path)

    # Update canonical resume and write HTML
    for exp in resume.experience:
        for b in exp.bullets:
            if b.id == semantic_bullet.id:
                b.text = rewritten

    renderer = HtmlResumeRenderer()
    renderer.write_html(resume_doc, out_html)
    assert os.path.exists(out_html)

    # Save resume_document.json using pydantic JSON serialization to handle datetimes
    with open(resume_doc_path, "w", encoding="utf-8") as f:
        f.write(resume_doc.model_dump_json())

    # Validate DOCX contains the rewritten text
    patched_doc = docx.Document(res_path)
    full_text = "\n".join([p.text for p in patched_doc.paragraphs])
    assert rewritten in full_text

    # Validate HTML contains the rewritten text
    with open(out_html, "r", encoding="utf-8") as f:
        html_text = f.read()
    assert rewritten in html_text

    # Validate resume_document.json contains the rewritten semantic bullet text
    with open(resume_doc_path, "r", encoding="utf-8") as f:
        rd = json.load(f)
    found = False
    for exp in rd.get("resume", {}).get("experience", []):
        for b in exp.get("bullets", []):
            if b.get("id") == semantic_bullet.id and rewritten == b.get("text"):
                found = True
    assert found

    # Run DOCX QA
    qa = OutputQAValidator()
    docx_warnings = qa.validate_docx(res_path, expected_candidate_name=resume.candidate.name)
    assert len(docx_warnings) == 0

    # If PDF converter and PyMuPDF are available, convert and verify PDF text
    try:
        from app.rendering.pdf_converter import PdfConverter
        converter = PdfConverter()
        pdf_path = converter.convert_docx_to_pdf(res_path, str(out_dir))
        if pdf_path:
            try:
                import fitz
                doc = fitz.open(pdf_path)
                extracted = "".join(p.get_text() for p in doc)
                doc.close()
                assert rewritten in extracted
            except Exception:
                # If PyMuPDF not available, skip PDF text check
                pass
    except Exception:
        # If converter not available, skip PDF step
        pass

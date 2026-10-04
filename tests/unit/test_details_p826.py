"""P8.26: plain parse issues, nothing hidden on Check details, lines the
parse couldn't place go where the user says, and read-back noise split
from real problems."""
from app.api.routes import plain_issue, unplaced_lines
from app.domain.resume import Candidate, Experience, Resume
from app.ingestion.docx import RawBlock, RawDocument
from app.rendering.document_map import DocumentLocation
from app.services.tailor import TailorService
from app.validation.output import OutputQAValidator


def test_parse_issues_in_plain_words():
    assert plain_issue("experience without a company (Nurse - ICU)") == \
        "We couldn't find the employer for \u201cNurse - ICU\u201d. Add it below."
    assert plain_issue("no candidate name") == "We couldn't find your name. Type it below."
    assert plain_issue("something new") == "something new"


def _raw(*texts):
    return RawDocument(filename="r.docx", blocks=[
        RawBlock(id=f"b{i}", block_type="paragraph", text=t, location=DocumentLocation(section="x"))
        for i, t in enumerate(texts)])


def test_unplaced_lines_and_placing_them():
    raw = _raw("Jane Doe", "Built dashboards", "Fluent in Portuguese and Swahili")
    resume = Resume(candidate=Candidate(name="Jane Doe"), experience=[
        Experience(id="exp_001", company="Acme", title="Analyst")])
    resume.experience[0].bullets = []
    lines = unplaced_lines(raw, resume)
    assert [l["text"] for l in lines] == ["Built dashboards", "Fluent in Portuguese and Swahili"]
    from app.domain.resume_document import ResumeDocument
    parsed = (raw, ResumeDocument(resume=resume), [])
    (_, doc, _ev), changed = TailorService(llm_client=None).apply_parse_corrections(
        parsed, {"placed": [{"id": "b1", "target": "exp_001"}, {"id": "b2", "target": "other"}]})
    r = doc.resume
    assert changed and [b.text for b in r.experience[0].bullets] == ["Built dashboards"]
    assert r.other_sections[0].heading == "Additional information"
    assert [l.text for l in r.other_sections[0].lines] == ["Fluent in Portuguese and Swahili"]


def test_read_back_problems_split_by_weight():
    assert OutputQAValidator.is_serious("ATS round-trip (DOCX): phone not found")
    assert OutputQAValidator.is_serious("ATS round-trip (PDF): 1 job entries read, 2 rendered")
    assert not OutputQAValidator.is_serious("ATS round-trip (DOCX): role titles or dates differ: x")
    assert not OutputQAValidator.is_serious("Content coverage: 1 line")


def test_section_headings_are_never_unplaced_lines():
    """P9.1 (review F1): every section heading was listed as a line "we
    couldn't place", and so added to the output under "Additional information"."""
    for path, expected in [("tests/fixtures/resumes/sample.docx", []),
                           ("tests/fixtures/resumes/replica_layout.pdf", []),
                           ("docs/user_testing/2026-10-02/resumes/teacher.docx", [])]:
        raw, doc, _ = TailorService(llm_client=None).parse_resume(path)
        assert [l["text"] for l in unplaced_lines(raw, doc.resume)] == expected, path


def test_a_line_left_out_is_not_added():
    raw = _raw("Jane Doe", "Fluent in Portuguese and Swahili")
    resume = Resume(candidate=Candidate(name="Jane Doe"))
    from app.domain.resume_document import ResumeDocument
    (_, doc, _ev), changed = TailorService(llm_client=None).apply_parse_corrections(
        (raw, ResumeDocument(resume=resume), []), {"placed": [{"id": "b1", "target": ""}]})
    assert doc.resume.other_sections == [] and not changed


def test_wrong_employer_and_lost_bullets_are_serious():
    """P9.1 (review F6): an ATS reading the wrong employer or losing bullets was only minor advice."""
    serious = OutputQAValidator.is_serious
    assert serious('ATS round-trip (PDF): company read as "acme inc" instead of "northwind"')
    assert serious('ATS round-trip (DOCX): 4 of 12 bullets not read back intact (e.g. "built")')
    assert not serious('ATS round-trip (DOCX): 1 of 12 bullets not read back intact (e.g. "built")')
    assert not serious("ATS round-trip (PDF): role titles or dates differ: Analyst Jan 2020 – Present")

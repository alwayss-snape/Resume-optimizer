from app.domain.resume import Candidate, Resume
from app.domain.resume_document import ResumeDocument, ResumePresentation, ResumeSource

def test_resume_document_has_versioned_json_snapshot():
    document = ResumeDocument(
        resume=Resume(candidate=Candidate(name="Avery Lee")),
        source=ResumeSource(filename="avery.docx", file_type="docx", import_mode="preserve"),
        presentation=ResumePresentation(template_id="ats-classic"),
    )
    revision = document.record_revision(
        "Imported résumé", ["resume", "source"], actor="import"
    )

    snapshot = document.snapshot()

    assert snapshot["schema_version"] == "1.0"
    assert snapshot["resume"]["candidate"]["name"] == "Avery Lee"
    assert snapshot["presentation"]["template_id"] == "ats-classic"
    assert snapshot["revisions"][0]["id"] == revision.id
    assert snapshot["revisions"][0]["actor"] == "import"


def test_resume_document_serializes_revision_timestamp_and_rejects_invalid_source():
    document = ResumeDocument(resume=Resume(candidate=Candidate(name="Avery Lee")))
    document.record_revision("Manual update", ["resume.summary"])
    snapshot = document.snapshot()

    assert isinstance(snapshot["revisions"][0]["created_at"], str)
    assert snapshot["revisions"][0]["changed_paths"] == ["resume.summary"]

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ResumeSource(filename="resume.txt", file_type="txt")

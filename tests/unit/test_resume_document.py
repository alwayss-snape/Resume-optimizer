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

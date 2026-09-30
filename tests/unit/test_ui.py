import pytest

def test_ui_importable():
    """Verify Streamlit app module can be imported without error."""
    import app.ui
    assert app.ui is not None


def test_ats_template_is_the_default_output():
    """P2.2: the ATS template is the default; PRESERVE is an opt-in under Advanced."""
    import inspect
    import os
    from streamlit.testing.v1 import AppTest
    from app.services.tailor import TailorService

    assert inspect.signature(TailorService.tailor_resume).parameters["mode"].default == "ATS_DEFAULT"
    at = AppTest.from_file(os.path.abspath("app/ui.py"), default_timeout=60)
    at.run()
    assert not at.exception
    assert not at.sidebar.radio  # no layout radio any more
    keep = [c for c in at.sidebar.checkbox if c.label == "Keep my original DOCX layout"]
    assert len(keep) == 1 and keep[0].value is False


def test_results_show_content_checks(tmp_path):
    """P2.6: the results screen lists the content checks."""
    import os
    from streamlit.testing.v1 import AppTest
    from app.validation.content_lint import ContentReport, LintIssue

    report = ContentReport(bullets=4, bullets_with_metrics=1, issues=[
        LintIssue(check="pronoun", where="Acme: \"I built…\"", message="Drop personal pronouns (I, my, we).")])
    at = AppTest.from_file(os.path.abspath("app/ui.py"), default_timeout=60)
    at.session_state["stage"] = "results"
    at.session_state["results"] = {"success": True, "alignment_score": "50.0", "initial_alignment_score": "40.0",
                                   "keyword_match": None, "docx": "", "pdf": "", "html": "", "changes_md": "",
                                   "warnings": [], "content_lint": report}
    at.run()
    assert not at.exception
    assert any(e.label == "Content checks: 1 suggestion(s)" for e in at.expander)
    assert any("Drop personal pronouns" in m.value for m in at.markdown)

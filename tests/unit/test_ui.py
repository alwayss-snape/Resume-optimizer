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

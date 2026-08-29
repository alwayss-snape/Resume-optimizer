import pytest

def test_ui_importable():
    """Verify Streamlit app module can be imported without error."""
    import app.ui
    assert app.ui is not None

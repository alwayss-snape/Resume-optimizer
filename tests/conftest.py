"""Test-wide isolation from the developer's .env.

Settings are read once at import time, and .env may point at a real cloud
provider with a real API key. Without this, any test that builds a default
TailorService/LLMClient would make live (paid, flaky) network calls. Real
environment variables take precedence over .env in pydantic-settings, so
setting them here, before app.config.settings is first imported, pins every
default client to an unreachable local Ollama with no cloud keys. Tests
that exercise a specific provider pass provider=/api_key= explicitly.
"""
import os
import tempfile

import pytest

os.environ["LLM_PROVIDER"] = "ollama"
os.environ["LLM_HOST"] = "http://127.0.0.1:9"  # discard port: fails fast, never reachable
os.environ["GROQ_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["SEMANTIC_MATCH_ENABLED"] = os.environ.get("SEMANTIC_MATCH_ENABLED", "true")
# Never read or write the developer's real confirmed-facts profile (P3.2).
os.environ["PROFILE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="profile_test_"), "facts.json")


@pytest.fixture(autouse=True)
def _no_daily_limit_between_tests():
    """The provider's daily-limit marker is process-wide (P8.23); one test
    hitting it must not switch the AI off for the next."""
    from app.llm import client as client_module
    client_module._DAILY_LIMIT_UNTIL.clear()
    yield
    client_module._DAILY_LIMIT_UNTIL.clear()


@pytest.fixture(autouse=True)
def _runs_in_tmp(tmp_path, monkeypatch):
    """A TailorService built with the default run folder (the CLI path) writes
    to this test's tmp dir, never to the real data/runs, which would keep
    copies of fixture resumes and JDs (P9.8 review)."""
    from app.services.run_manager import RunManager
    monkeypatch.setattr(RunManager.__init__, "__defaults__", (str(tmp_path / "runs"),))

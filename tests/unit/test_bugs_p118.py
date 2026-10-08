"""P11.8: bugs found in the owner's 2026-10-08 runs."""
import os

import pytest
from fastapi.testclient import TestClient

from app.analysis.rewriter import keep_past_tense
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.rendering.page_fit import PageFitter


def test_finished_work_in_a_current_job_stays_in_the_past_tense():
    assert keep_past_tense("Deployed scalable ML infra", "Deploy scalable ML infra on Spark") == \
        "Deployed scalable ML infra on Spark"
    assert keep_past_tense("Built a scoring pipeline", "Build a scoring pipeline") == "Built a scoring pipeline"
    assert keep_past_tense("Made inference reusable", "Make inference reusable") == "Made inference reusable"
    assert keep_past_tense("Lead a lab of 4", "Lead a 4-person lab") == "Lead a 4-person lab"  # present stays
    assert keep_past_tense("Built X", "Designed X") == "Designed X"  # a different verb is the model's call


def test_a_projects_opening_bullet_is_trimmed_last():
    bullets = [ResumeBullet(id=f"b{i}", text=t, group="Fraud Detection") for i, t in
               enumerate(["Built and deployed a fraud model", "Routed 90% of cases", "Cut onboarding by 60%"])]
    resume = Resume(candidate=Candidate(name="A B"), experience=[
        Experience(id="e1", company="Acme", title="DS", start_date="Jan 2020", end_date="Present", bullets=bullets)])
    relevance = {"b0": 0.0, "b1": 0.9, "b2": 0.8}  # the opening bullet scores lowest
    PageFitter._trim_bullets(resume, 10_000, relevance, set())
    assert resume.experience[0].bullets[0].text == "Built and deployed a fraud model"


@pytest.mark.skipif(not os.path.isdir("web/dist"), reason="web bundle not built")
def test_the_page_is_revalidated_and_the_bundle_cached():
    from app.api.main import create_app
    client = TestClient(create_app())
    page = client.get("/")
    assert page.headers["cache-control"] == "no-cache"
    asset = next(f for f in os.listdir("web/dist/assets") if f.endswith(".js"))
    assert "immutable" in client.get(f"/assets/{asset}").headers["cache-control"]
    assert client.get("/api/health").headers.get("cache-control") != "no-cache"

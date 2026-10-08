"""P11.2: the interview, asked before anything is written."""
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.analysis.interview import InterviewAnswer, apply_interview, build_interview
from app.analysis.role_brief import checked_brief
from app.domain.job import JobDescription
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.tailoring import ProjectChoice
from app.llm.schemas import RoleBriefResult
from app.services.profile_store import MemoryProfileStore
from app.services.tailor import TailorService

POST = "Senior Data Scientist to solve pricing and inventory management problems at scale."
JD = JobDescription(raw_text=POST, job_title="Senior Data Scientist", keywords=["pricing"])
BRIEF = checked_brief(RoleBriefResult(target_title="Senior Data Scientist", competencies=[
    {"name": "Pricing analytics", "kind": "stated", "jd_words": "pricing", "look_for": ["price", "discount", "ratio"]},
    {"name": "Demand forecasting", "kind": "inferred", "jd_words": "inventory management", "look_for": ["forecast", "demand"]},
]), JD)


def _resume():
    bullets = [ResumeBullet(id="b1", text="Built weekly demand forecast models for 500 stores.", group="Forecasting"),
               ResumeBullet(id="b2", text="Ranked product pairs to suggest bundles and placement.", group="Basket Analysis"),
               ResumeBullet(id="b3", text="Built a monitoring agent for pipelines.", group="Model Monitor")]
    return Resume(candidate=Candidate(name="A B"), experience=[
        Experience(id="e1", company="Acme", title="DS", start_date="Jan 2022", end_date="Present", bullets=bullets)])


def _choices(kept):
    return [ProjectChoice(key=f"e1::{n}", experience_id="e1", job="Acme", name=n, chosen=n in kept)
            for n in ("Forecasting", "Basket Analysis", "Model Monitor")]


def test_asks_about_a_need_nothing_shows_at_the_closest_project_and_for_missing_figures():
    brief = BRIEF.model_copy(update={"project_evidence": {
        "e1::Forecasting": [{"competency": "Demand forecasting", "quote": "weekly demand forecast models"}]}})
    vec = lambda t: [0.0, 1.0] if ("pric" in t.lower() or "bundle" in t.lower()) else [1.0, 0.0]
    questions = build_interview(_resume(), brief, _choices({"Forecasting", "Basket Analysis", "Model Monitor"}),
                                embedder=lambda ts: [vec(t) for t in ts])
    need = [q for q in questions if q.kind == "need"]
    assert [q.competency for q in need] == ["Pricing analytics"]  # forecasting is shown already
    assert need[0].project == "Basket Analysis" and "price, discount, ratio" in need[0].question
    figures = [q.project for q in questions if q.kind == "figure"]
    assert figures == ["Basket Analysis", "Model Monitor"]  # "500 stores" has a figure


def test_an_answer_becomes_a_bullet_of_its_project_and_shows_the_need():
    resume, evidence = _resume(), []
    brief = BRIEF.model_copy(deep=True)
    vec = lambda t: [0.0, 1.0] if ("pric" in t.lower() or "bundle" in t.lower()) else [1.0, 0.0]
    questions = build_interview(resume, brief, _choices({"Forecasting", "Basket Analysis"}),
                                embedder=lambda ts: [vec(t) for t in ts])
    need = next(q for q in questions if q.kind == "need" and q.competency == "Pricing analytics")
    notes = apply_interview(resume, evidence, brief, questions, [
        InterviewAnswer(id=need.id, answer="  Set the fee tiers;\norders rose 6%. "),
        InterviewAnswer(id="unknown", answer="ignored")])
    added = [b for b in resume.experience[0].bullets if b.id.startswith("e1_q")]
    assert [(b.text, b.group) for b in added] == [("Set the fee tiers; orders rose 6%.", need.project)]
    assert any(e.source_id == added[0].id for e in evidence)
    assert brief.project_evidence[f"e1::{need.project}"][0]["competency"] == "Pricing analytics"
    assert notes == [f"Added your answer to {need.project} (Pricing analytics)"]


def test_answers_are_saved_and_offered_next_time():
    store = MemoryProfileStore()
    questions = build_interview(_resume(), BRIEF, _choices({"Forecasting", "Basket Analysis"}))
    store.record_interview(questions, [InterviewAnswer(id=questions[0].id, answer="Priced the membership tiers")])
    again = build_interview(_resume(), BRIEF, _choices({"Forecasting", "Basket Analysis"}))
    store.prefill_interview(again)
    assert again[0].saved_answer == "Priced the membership tiers"


def test_prepare_then_draft_with_answers_through_the_api(tmp_path):
    from app.api.main import create_app
    from app.services.run_manager import RunManager
    from tests.unit.test_api import _events

    def make_service(model=None):
        service = TailorService(llm_client=None)
        service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
        service.profile_store = MemoryProfileStore()
        service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
        return service

    with TestClient(create_app(make_service=make_service, serve_web=False)) as client, \
            open("tests/fixtures/resumes/replica_layout.pdf", "rb") as f:
        assert client.post("/api/parse", files={"file": ("cv.pdf", f, "application/pdf")},
                           data={"jd_text": "Senior Data Scientist. Pricing and demand forecasting."}).status_code == 200
        prepared = _events(client.post("/api/prepare", json={}))[-1][1]
        figure = next(q for q in prepared["questions"] if q["kind"] == "figure")
        answer = {"id": figure["id"], "answer": "Served 40 stores", "experience_id": ""}
        session = lambda: client.app.state.sessions.get(client.cookies.get("rt_session"))
        texts = lambda: [b.text for e in session().data["parsed"][1].resume.experience for b in e.bullets]
        _events(client.post("/api/proposals", json={"answers": [answer]}))
        assert texts().count("Served 40 stores") == 1
        # Drafting again starts from before the answers: the answer isn't added twice.
        _events(client.post("/api/proposals", json={"answers": [answer]}))
        assert texts().count("Served 40 stores") == 1


def test_a_needs_answer_goes_where_the_user_says():
    resume, evidence = _resume(), []
    questions = build_interview(resume, BRIEF.model_copy(deep=True), _choices({"Forecasting", "Basket Analysis"}))
    need = next(q for q in questions if q.kind == "need")
    assert "comes closest" not in need.question  # the guess is a starting choice, never a claim
    assert {o["label"] for o in need.options} >= {"Model Monitor (Acme)", "Elsewhere at Acme"}
    apply_interview(resume, evidence, BRIEF.model_copy(deep=True), questions, [
        InterviewAnswer(id=need.id, answer="Priced the monitoring tiers", experience_id="e1", project="Model Monitor")])
    added = next(b for b in resume.experience[0].bullets if b.text == "Priced the monitoring tiers")
    assert added.group == "Model Monitor"

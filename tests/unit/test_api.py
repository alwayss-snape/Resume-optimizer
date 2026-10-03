"""Web API (P5.1): the full flow through HTTP, plus the shared form helpers.

No LLM (the default client points at an unreachable Ollama, see conftest)
and no LibreOffice (PDF conversion is stubbed out)."""
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.api import forms
from app.api.main import create_app
from app.api.routes import SESSION_COOKIE
from app.api.sessions import SessionStore
from app.services.run_manager import RunManager
from app.services.tailor import TailorService

SAMPLE_DOCX = "tests/fixtures/resumes/sample.docx"
REPLICA_PDF = "tests/fixtures/resumes/replica_layout.pdf"
with open("tests/fixtures/jds/sample.txt", encoding="utf-8") as _f:
    SAMPLE_JD = _f.read()


@pytest.fixture
def client(tmp_path):
    def make_service(model=None):
        service = TailorService(llm_client=None)
        service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
        service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
        return service

    app = create_app(make_service=make_service, serve_web=False)
    with TestClient(app) as c:
        yield c


def _upload(path, name=None):
    with open(path, "rb") as f:
        return {"file": (name or path.rsplit("/", 1)[-1], f.read())}


def _events(response):
    """SSE body -> [(event, data), ...]."""
    out = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def _parse(client, path=SAMPLE_DOCX):
    r = client.post("/api/parse", files=_upload(path), data={"jd_text": SAMPLE_JD})
    assert r.status_code == 200, r.text
    return r.json()


def _draft(client, corrections=None):
    r = client.post("/api/proposals", json={"corrections": corrections})
    assert r.status_code == 200, r.text
    events = _events(r)
    assert events[-1][0] == "result", events[-1]
    return events


def test_config_lists_models_for_the_configured_provider(client):
    body = client.get("/api/config").json()
    assert body["provider"] == "ollama"
    assert body["models"] == forms.model_options("ollama")
    assert body["max_upload_mb"] == 5


def test_full_flow_parse_draft_preview_tailor_download(client):
    parsed = _parse(client)
    assert client.cookies.get(SESSION_COOKIE)
    details = parsed["details"]
    assert details["experience"] and details["experience"][0]["roles"]

    first = details["experience"][0]
    events = _draft(client, {"candidate": {**details["candidate"], "headline": "Data Engineer"},
                             "experience": [{"id": first["id"], "company": first["company"],
                                             "location": first["location"], "roles": first["roles"]}]})
    assert any(kind == "progress" for kind, _ in events)
    result = events[-1][1]
    assert result["proposals"] and result["keyword_match"]["rows"]
    card = result["proposals"][0]
    assert {"id", "state", "state_label", "diff", "section"} <= set(card)
    assert all({"text"} <= set(span) for span in card["diff"]["proposed"])
    assert result["llm"]["available"] is False and result["llm"]["fix_hint"]

    selection = [{"id": p["id"]} for p in result["proposals"]]
    preview = client.post("/api/match-preview", json={"selection": selection}).json()
    assert 0 <= preview["rate"] <= 100 and "delta" in preview

    r = client.post("/api/tailor", json={"selection": selection})
    assert r.status_code == 200, r.text
    kind, final = _events(r)[-1]
    assert kind == "result", final
    assert final["files"] == {"docx": True, "pdf": False, "changes": True}
    assert final["alignment_score"] >= 0

    docx = client.get("/api/files/docx")
    assert docx.status_code == 200 and docx.content.startswith(b"PK")
    assert "attachment" in docx.headers["content-disposition"]
    assert client.get("/api/files/pdf").status_code == 404
    assert client.get("/api/files/secrets").status_code == 404


def test_pdf_upload_parses(client):
    assert _parse(client, REPLICA_PDF)["details"]["candidate"]["name"]


def test_steps_need_a_session(client):
    assert client.post("/api/proposals", json={}).status_code == 404
    assert client.get("/api/files/docx").status_code == 404


def test_tailor_before_drafting_is_refused(client):
    _parse(client)
    assert client.post("/api/tailor", json={}).status_code == 409


@pytest.mark.parametrize("name,content,status", [
    ("resume.pages", b"hello", 415),  # .txt is read since P8.22
    ("resume.txt", b"\x00\x01binary\x00", 415),
    ("resume.pdf", b"PK\x03\x04 not a pdf", 415),
    ("resume.docx", b"%PDF-1.7 not a docx", 415),
])
def test_bad_uploads_are_refused(client, name, content, status):
    r = client.post("/api/parse", files={"file": (name, content)}, data={"jd_text": SAMPLE_JD})
    assert r.status_code == status


def test_oversized_upload_and_empty_jd_are_refused(client):
    client.app.state.max_upload_bytes = 10
    assert client.post("/api/parse", files=_upload(SAMPLE_DOCX), data={"jd_text": SAMPLE_JD}).status_code == 413
    client.app.state.max_upload_bytes = 5 * 1024 * 1024
    assert client.post("/api/parse", files=_upload(SAMPLE_DOCX), data={"jd_text": "  "}).status_code == 422


def test_unknown_model_is_refused(client):
    r = client.post("/api/parse", files=_upload(SAMPLE_DOCX), data={"jd_text": SAMPLE_JD, "model": "gpt-9"})
    assert r.status_code == 422


def test_invalid_new_role_is_refused_before_any_work(client):
    _parse(client)
    result = _draft(client)[-1][1]
    r = client.post("/api/tailor", json={"selection": [{"id": result["proposals"][0]["id"]}],
                                         "new_role": {"company": "Acme"}})
    assert r.status_code == 422 and "job title" in r.json()["detail"]


def test_rate_limit(tmp_path):
    app = create_app(make_service=lambda model=None: TailorService(llm_client=None), rate_limit=1, serve_web=False)
    with TestClient(app) as c:
        assert c.post("/api/parse", files=_upload(SAMPLE_DOCX), data={"jd_text": SAMPLE_JD}).status_code == 200
        assert c.post("/api/parse", files=_upload(SAMPLE_DOCX), data={"jd_text": SAMPLE_JD}).status_code == 429


def test_preview_renders_pdf_pages(client, tmp_path):
    _parse(client)
    pdf_path = str(tmp_path / "out.pdf")
    doc = pymupdf.open()
    for _ in range(2):
        doc.new_page(width=595, height=842)
    doc.save(pdf_path)
    session = client.app.state.sessions.get(client.cookies.get(SESSION_COOKIE))
    session.data["results"] = {"pdf": pdf_path}
    r = client.get("/api/preview/2")
    assert r.status_code == 200 and r.content.startswith(b"\x89PNG")
    assert client.get("/api/preview/3").status_code == 404


def test_reset_deletes_temp_files(client):
    import os
    _parse(client)
    session = client.app.state.sessions.get(client.cookies.get(SESSION_COOKIE))
    path = session.data["resume_path"]
    assert os.path.exists(path)
    assert client.post("/api/reset").status_code == 200
    assert not os.path.exists(path) and session.data == {}


def test_expired_sessions_are_swept_with_their_files(tmp_path):
    store = SessionStore(ttl_seconds=10)
    session = store.create()
    upload = tmp_path / "resume.pdf"
    upload.write_bytes(b"%PDF")
    session.data["resume_path"] = str(upload)
    assert store.sweep(now=session.touched + 5) == 0
    session.busy.acquire()  # a running step keeps its session
    assert store.sweep(now=session.touched + 11) == 0
    session.busy.release()
    assert store.sweep(now=session.touched + 11) == 1
    assert not upload.exists() and len(store) == 0


# --- form helpers --------------------------------------------------------------

def _question(**kw):
    return SimpleNamespace(**{"id": "gap_1", "keywords": ["Airflow", "dbt"], "saved_answer": "", **kw})


def test_gap_answers_count_only_confirmed_input():
    q = _question(saved_answer="Used it at Acme")
    inputs = {"gap_1": {"ticked": [], "answer": "Used it at Acme", "target": "auto"}}
    assert forms.gap_answers([q], inputs, []) == []  # pre-fill unchanged and nothing ticked
    inputs = {"gap_1": {"ticked": ["Airflow", "Kafka"], "answer": "", "target": "exp_9"}}
    assert forms.gap_answers([q], inputs, ["exp_1"]) == [
        {"question_id": "gap_1", "confirmed_keywords": ["Airflow"], "answer": "", "target": "auto"}]


def test_resolve_target_rejects_unknown_ids():
    assert forms.resolve_target("exp_1", ["exp_1"]) == "exp_1"
    assert forms.resolve_target("new_project", []) == "new_project"
    assert forms.resolve_target("../etc", ["exp_1"]) == "auto"


def test_new_role_validation():
    assert forms.new_role() == (None, None)
    role, error = forms.new_role(company="Acme")
    assert role is None and "job title" in error
    role, error = forms.new_role("Acme", "Engineer", "", False, date(2023, 5, 1), date(2022, 1, 1), "Built X")
    assert "before its start" in error
    role, error = forms.new_role("Acme", "Engineer", "Pune", True, date(2023, 5, 1), None, "Built X")
    assert error is None and role["start_date"] == "May 2023" and role["end_date"] == ""


def test_preapproved_carries_edits():
    from app.analysis.change_proposal import ChangeProposal
    p = ChangeProposal(original_text="Did A", proposed_text="Delivered A")
    kept, edited = forms.preapproved([p]), forms.preapproved([p], {p.id: "Shipped A"})
    assert kept[0]["proposed_text"] == "Delivered A" and not kept[0]["user_edited"]
    assert edited[0]["proposed_text"] == "Shipped A" and edited[0]["user_edited"]
    assert "rewritten_text" not in edited[0]


def test_failing_service_does_not_lock_the_session(client):
    """Review fix: a step that fails before its worker starts must release
    the session, or every later request gets 409."""
    _parse(client)
    good = client.app.state.make_service
    client.app.state.make_service = MagicMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        client.post("/api/proposals", json={})
    client.app.state.make_service = good
    assert _draft(client)[-1][0] == "result"


def test_worker_errors_are_generic_and_release_the_lock(client):
    _parse(client)
    session = client.app.state.sessions.get(client.cookies.get(SESSION_COOKIE))
    session.data["parsed"] = "not a parse"  # makes generate_proposals fail inside the worker
    kind, payload = _events(client.post("/api/proposals", json={}))[-1]
    assert kind == "error" and "not a parse" not in payload["message"]
    assert not session.busy.locked()


def test_saved_answers_stay_with_their_visitor(client, tmp_path):
    """Review fix: confirmed gap answers are per session, never shared."""
    from app.analysis.gap_questions import GapQuestion
    _parse(client)
    mine = client.app.state.sessions.get(client.cookies.get(SESSION_COOKIE))
    q = GapQuestion(id="gap_1", requirement="Kafka", priority="required", keywords=["Kafka"], question="?")
    mine.profile.record([{"question_id": "gap_1", "confirmed_keywords": ["Kafka"], "answer": "At Acme"}], [q])
    other = client.app.state.sessions.create()
    assert other.profile.known(["Kafka"]) == {}
    assert mine.profile.known(["Kafka"])["Kafka"].answer == "At Acme"


def test_failed_first_parse_leaves_no_session(client):
    client.app.state.make_service = MagicMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        client.post("/api/parse", files=_upload(SAMPLE_DOCX), data={"jd_text": SAMPLE_JD})
    assert len(client.app.state.sessions) == 0


def test_cookie_is_refreshed_on_activity(client):
    _parse(client)
    r = client.get("/api/files/docx")  # 404, but the session is alive
    assert SESSION_COOKIE in r.headers.get("set-cookie", "")


def test_reset_during_a_running_step_happens_when_it_ends(client):
    """P5.3 review: Start over while drafting must still clear the session."""
    import os
    _parse(client)
    session = client.app.state.sessions.get(client.cookies.get(SESSION_COOKIE))
    path = session.data["resume_path"]
    session.busy.acquire()  # a step is running
    assert client.post("/api/reset").json() == {"ok": True, "pending": True}
    assert os.path.exists(path)
    session.busy.release()
    # The next streaming step's end performs the pending reset.
    session.reset_pending = True
    session.data["parsed"] = "not a parse"
    _events(client.post("/api/proposals", json={}))
    assert session.data == {} and not os.path.exists(path)


def test_drafting_again_keeps_earlier_corrections(client):
    """P5.3 review: going back and drafting again must not forget fixes."""
    details = _parse(client)["details"]
    _draft(client, {"candidate": {**details["candidate"], "headline": "Data Engineer"}, "experience": []})
    session = client.app.state.sessions.get(client.cookies.get(SESSION_COOKIE))
    assert session.data["parse_corrected"] is True
    _draft(client, {"candidate": {**details["candidate"], "headline": "Data Engineer"}, "experience": []})
    assert session.data["parse_corrected"] is True


def test_an_added_job_comes_back_as_an_ordinary_one(client):
    """Drafting returns the corrected details, so the form shows an added job
    with an id (sending it again would add it twice); an incomplete one is a
    plain error."""
    details = _parse(client)["details"]
    job = {"company": "Northwind", "title": "Data Analyst", "location": "", "current": True,
           "start_date": "March 2019", "end_date": "Present", "description": "Built churn dashboards"}
    events = _draft(client, {**details, "added_jobs": [job]})
    back = events[-1][1]["details"]["experience"]
    added = [e for e in back if e["company"] == "Northwind"]
    assert len(back) == len(details["experience"]) + 1 and added[0]["bullets"] == 1 and added[0]["id"]

    r = client.post("/api/proposals", json={"corrections": {**details, "added_jobs": [{**job, "start_date": ""}]}})
    assert _events(r)[-1] == ("error", {"message": "A new job needs a start date."})


def test_arrange_after_tailoring(client):
    """P8.13: the result carries what the Arrange screen edits; a layout
    re-renders the files with no LLM call; arranging before generating is
    refused."""
    assert client.post("/api/arrange", json={"layout": {}}).status_code in (404, 409)  # no session yet
    _parse(client)
    result = _draft(client)[-1][1]
    final = _events(client.post("/api/tailor", json={"selection": [{"id": p["id"]} for p in result["proposals"]]}))[-1][1]
    arrangement = final["arrangement"]
    assert arrangement and arrangement["sections"] and arrangement["layout"]["section_order"]
    jobs = next(s for s in arrangement["sections"] if s["key"] == "experience")
    job = jobs["entries"][0]
    layout = dict(arrangement["layout"])
    layout["bullet_order"] = {**layout["bullet_order"], job["id"]: [b["id"] for b in reversed(job["bullets"])]}
    layout["hidden_sections"] = ["summary"]
    r = client.post("/api/arrange", json={"layout": layout})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["files"]["docx"] and out["arrangement"]["layout"]["hidden_sections"] == ["summary"]
    assert client.post("/api/arrange", json={"layout": {**layout, "page_target": 9}}).status_code == 422


def test_very_short_job_description_is_refused(client):
    r = client.post("/api/analyze", files=_upload(SAMPLE_DOCX), data={"jd_text": "Data Analyst"})
    assert r.status_code == 422 and "very short" in r.json()["detail"]


def test_upload_edge_cases(client, tmp_path):
    """P8.22: broken files get their own message, pasted text and a renamed .doc work."""
    UT = "docs/user_testing/2026-10-02/resumes/"
    r = client.post("/api/analyze", files=_upload(UT + "corrupt.docx"), data={"jd_text": SAMPLE_JD})
    assert r.status_code == 422 and "damaged" in r.json()["detail"]
    r = client.post("/api/analyze", files=_upload(UT + "encrypted.pdf"), data={"jd_text": SAMPLE_JD})
    assert r.status_code == 422 and "password" in r.json()["detail"]
    r = client.post("/api/analyze", data={"jd_text": SAMPLE_JD, "resume_text": "Jane Doe\njane@example.com\n\n"
                                          "EXPERIENCE\nData Engineer | Acme | 2020 - Present\n- Built Spark pipelines"})
    assert r.status_code == 200, r.text
    r = client.post("/api/analyze", files=_upload(UT + "renamed.doc"), data={"jd_text": SAMPLE_JD})
    assert r.status_code == 200, r.text
    assert client.post("/api/analyze", data={"jd_text": SAMPLE_JD}).status_code == 422  # nothing to read

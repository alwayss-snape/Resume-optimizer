"""P11.14: the same input keeps the same brief, map and projects within a session."""
from app.analysis.project_select import select_projects
from app.domain.tailoring import TailoringAction
from app.llm.schemas import ProjectEvidenceResult, RoleBriefResult
from app.services.tailor import TailorService

from tests.unit.test_project_select_p1013 import BANK, REPLICA
from tests.unit.test_role_brief_p113 import POST, _result


class _DriftingLLM:
    """Recorded answers, except the map names a different project each call,
    as a live model sometimes does on the same input."""
    provider, model, last_error, on_wait = "fake", "fake", None, None

    def __init__(self):
        self.calls = {"brief": 0, "map": 0}

    def is_available(self):
        return True

    def get_usage_summary(self):
        return {}

    def generate_json(self, messages, schema_model, **kwargs):
        if schema_model is RoleBriefResult:
            self.calls["brief"] += 1
            return _result(competencies=[
                {"name": "Pricing analytics", "kind": "stated", "jd_words": "pricing", "look_for": ["price"]},
                {"name": "Demand forecasting", "kind": "inferred", "jd_words": "inventory management",
                 "look_for": ["forecast", "demand"]}])
        if schema_model is ProjectEvidenceResult:
            n = self.calls["map"]
            self.calls["map"] += 1
            listing = [l for l in messages[-1]["content"].splitlines() if l[:1].isdigit()]
            pick = n % len(listing)
            bullet = messages[-1]["content"].split(listing[pick], 1)[1].splitlines()[1].strip(" -")
            quote = " ".join(bullet.split()[1:4])
            return ProjectEvidenceResult(projects=[
                {"project": pick, "shows": [{"competency": "Demand forecasting", "quote": quote},
                                            {"competency": "Pricing analytics", "quote": quote}]}])
        raise RuntimeError("not recorded")  # the job reading falls back to rules


def _run(service, parsed):
    prepared = service.prepare(parsed, POST)
    resume = parsed[1].resume
    actions = [TailoringAction(action="REWRITE", source_id=b.id, relevance=0.2)
               for e in resume.experience for b in e.bullets]
    chosen = [c.name for c in select_projects(resume, actions, prepared["job_description"],
                                              brief=prepared["role_brief"]) if c.chosen]
    return prepared["role_brief"], chosen


def _parsed(service):
    parsed, _ = service.apply_parse_corrections(service.parse_resume(REPLICA), {"added_jobs": [BANK]})
    return parsed


def test_two_runs_in_a_session_keep_the_same_projects():
    llm = _DriftingLLM()
    service = TailorService(llm_client=llm)
    service.ai_cache = {}
    parsed = _parsed(service)
    brief1, kept1 = _run(service, parsed)
    brief2, kept2 = _run(service, parsed)
    assert brief1.project_evidence and brief1.project_evidence == brief2.project_evidence
    assert kept1 == kept2
    assert llm.calls == {"brief": 1, "map": 1}  # the second run reused both answers


def test_without_the_cache_the_drift_shows_so_the_test_above_means_something():
    llm = _DriftingLLM()
    service = TailorService(llm_client=llm)
    parsed = _parsed(service)
    brief1, _ = _run(service, parsed)
    brief2, _ = _run(service, parsed)
    assert brief1.project_evidence != brief2.project_evidence


def test_a_fallback_is_not_kept_and_a_new_input_is_asked_again():
    class _Offline(_DriftingLLM):
        def is_available(self):
            return False
    service = TailorService(llm_client=_Offline())
    service.ai_cache = {}
    parsed = _parsed(service)
    _run(service, parsed)
    assert not any(k.startswith("brief:") for k in service.ai_cache)  # the heuristic brief isn't pinned
    llm = _DriftingLLM()
    service.llm_client = llm
    service.jd_analyzer.llm_client = llm
    _run(service, parsed)
    service.prepare(parsed, POST + " Experience with demand forecasting is a plus.")
    assert llm.calls["brief"] == 2  # a different job is a new question


def test_start_over_forgets_the_cache():
    from app.api.sessions import Session
    session = Session(id="s")
    session.ai_cache["brief:x"] = "answer"
    session.reset()
    assert session.ai_cache == {}


def test_groq_calls_at_temperature_zero_send_a_fixed_seed():
    from app.llm.client import LLMClient
    sent = {}

    class _Resp:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}], "usage": {}}

    def post(url, json=None, **kw):
        sent.update(json)
        return _Resp()

    client = LLMClient(provider="groq", model="openai/gpt-oss-120b", api_key="k")
    client._http = type("H", (), {"post": staticmethod(post)})()
    try:
        client._generate_groq([{"role": "user", "content": "hi"}], temperature=0.0, response_format=None)
    except Exception:
        pass
    assert sent.get("seed") == 0


def test_a_failed_map_call_is_asked_again_review_p1114():
    """Review finding: a map call that failed once left the session with no map."""
    class _FailsOnce(_DriftingLLM):
        def generate_json(self, messages, schema_model, **kwargs):
            if schema_model is ProjectEvidenceResult and self.calls["map"] == 0:
                self.calls["map"] += 1
                raise RuntimeError("429 rate limited")
            return super().generate_json(messages, schema_model, **kwargs)
    llm = _FailsOnce()
    service = TailorService(llm_client=llm)
    service.ai_cache = {}
    parsed = _parsed(service)
    first, _ = _run(service, parsed)
    second, _ = _run(service, parsed)
    third, _ = _run(service, parsed)
    assert first.project_evidence == {} and second.project_evidence
    assert second.project_evidence == third.project_evidence
    assert llm.calls == {"brief": 1, "map": 2}

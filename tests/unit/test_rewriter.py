from unittest.mock import MagicMock, patch

import pytest
from app.analysis.rewriter import LLMRewriter, RewriteProposal
from app.domain.evidence import Evidence
from app.domain.job import JobDescription, Requirement
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.tailoring import TailoringAction, TailoringPlan
from app.llm.client import LLMClient

def test_rewriter_deterministic_fallback():
    rewriter = LLMRewriter(llm_client=None)

    resume = Resume(
        candidate=Candidate(name="Jane Doe"),
        experience=[
            Experience(
                id="exp_001",
                company="Acme",
                title="Engineer",
                bullets=[
                    ResumeBullet(id="exp_001_b01", text="Built API microservices in Python processing 50M requests."),
                ],
            )
        ],
    )

    evidence_list = [
        Evidence(id="ev_001", source_type="experience", source_id="exp_001_b01", text="Built API microservices in Python processing 50M requests."),
    ]

    jd = JobDescription(
        job_title="Python Engineer",
        requirements=[Requirement(id="req_001", text="Python API", category="skill")],
        raw_text="Test JD",
    )

    plan = TailoringPlan(
        actions=[
            TailoringAction(
                action="REWRITE",
                source_id="exp_001_b01",
                evidence_ids=["ev_001"],
                rationale="Align with API requirement",
            )
        ]
    )

    proposals = rewriter.execute_plan(resume, plan, evidence_list, jd)
    assert len(proposals) == 1
    prop = proposals[0]
    assert isinstance(prop, RewriteProposal)
    assert prop.source_id == "exp_001_b01"
    # Fallback preserves original text when LLM unavailable
    assert prop.rewritten_text == prop.original_text

@patch("ollama.Client")
def test_rewrite_bullet_parses_structured_json_when_llm_available(mock_ollama):
    """rewrite_bullet must parse the JSON {rewritten, rationale, evidence_ids}
    the prompt asks for, not treat the raw LLM response as the bullet text."""
    mock_inst = MagicMock()
    mock_inst.list.return_value = {"models": [{"name": "qwen3:4b"}]}
    mock_inst.chat.return_value = {
        "message": {
            "content": (
                '{"rewritten": "Architected an automated pipeline supporting '
                'Mortgage Cadence LOS workflows.", "rationale": "Surfaces the '
                'Mortgage Cadence keyword from the JD.", "evidence_ids": ["ev_001"]}'
            )
        },
    }
    mock_ollama.return_value = mock_inst

    client = LLMClient(model="qwen3:4b", provider="ollama")
    rewriter = LLMRewriter(llm_client=client)
    evidence = [Evidence(id="ev_001", source_type="experience", source_id="exp_001_b01", text="Acme: Built a pipeline.")]

    rewritten, rationale = rewriter.rewrite_bullet(
        "Built a pipeline.", evidence, ["Mortgage Cadence LOS"], target_keywords=["Mortgage Cadence"],
    )

    assert rewritten == "Architected an automated pipeline supporting Mortgage Cadence LOS workflows."
    assert rationale == "Surfaces the Mortgage Cadence keyword from the JD."


@patch("ollama.Client")
def test_rewrite_bullet_falls_back_when_llm_unreachable(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.list.side_effect = Exception("connection refused")
    mock_ollama.return_value = mock_inst

    client = LLMClient(model="qwen3:4b", provider="ollama")
    rewriter = LLMRewriter(llm_client=client)

    rewritten, rationale = rewriter.rewrite_bullet("Built a pipeline.", [], [])
    assert rewritten == "Built a pipeline."
    assert rationale == ""


def test_rewrite_status_reports_unavailable_llm_with_reason():
    from app.analysis.rewriter import STATUS_LLM_UNAVAILABLE
    client = MagicMock()
    client.is_available.return_value = False
    client.last_error = "GROQ_API_KEY is not set"
    text, _, status, error = LLMRewriter(client).rewrite_bullet_with_status("Built X.", [], [])
    assert text == "Built X." and status == STATUS_LLM_UNAVAILABLE and error == "GROQ_API_KEY is not set"


def test_rewrite_status_reports_llm_error():
    from app.analysis.rewriter import STATUS_LLM_ERROR
    client = MagicMock()
    client.is_available.return_value = True
    client.generate_json.side_effect = Exception("429 rate limited")
    text, _, status, error = LLMRewriter(client).rewrite_bullet_with_status("Built X.", [], [])
    assert text == "Built X." and status == STATUS_LLM_ERROR and "429" in error


def test_rewrite_status_ok_and_unchanged():
    from app.analysis.rewriter import STATUS_OK, STATUS_UNCHANGED
    from app.llm.schemas import BulletRewriteResult
    client = MagicMock()
    client.is_available.return_value = True
    client.generate_json.return_value = BulletRewriteResult(rewritten="Engineered X.", rationale="r")
    assert LLMRewriter(client).rewrite_bullet_with_status("Built X.", [], [])[2] == STATUS_OK
    client.generate_json.return_value = BulletRewriteResult(rewritten="Built X.", rationale="r")
    assert LLMRewriter(client).rewrite_bullet_with_status("Built X.", [], [])[2] == STATUS_UNCHANGED


def test_normalize_llm_text_fixes_typographic_unicode():
    from app.analysis.rewriter import normalize_llm_text
    raw = "Architected high‑throughput services processing over 50 M daily requests, cutting cost 2 x."
    out = normalize_llm_text(raw)
    assert out == "Architected high-throughput services processing over 50M daily requests, cutting cost 2 x."
    assert all(ord(c) < 128 for c in out)


# -- Rewrite v2: one call per role (P1.4) ---------------------------------

def _role_setup():
    from app.analysis.tailor_planner import TailoringPlanner
    from app.domain.evidence import Evidence
    from app.domain.job import JobDescription, Requirement
    from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
    resume = Resume(candidate=Candidate(name="J"), experience=[Experience(
        id="e1", company="Acme", title="Data Scientist", bullets=[
            ResumeBullet(id="b1", text="Built LightGBM models in Python for fraud."),
            ResumeBullet(id="b2", text="Built Spark pipelines for feature data."),
            ResumeBullet(id="b3", text="Organised the team offsite."),
        ])])
    evidence = [Evidence(id=f"ev_{b.id}", source_type="experience", source_id=b.id, text=b.text)
                for b in resume.experience[0].bullets]
    reqs = [Requirement(id="r1", text="LightGBM and Python modeling"), Requirement(id="r2", text="Spark pipelines")]
    job = JobDescription(requirements=reqs, keywords=["LightGBM", "Python", "Spark"], raw_text="x")
    plan = TailoringPlanner().create_plan(resume, job, evidence, matches=[])
    return resume, evidence, job, plan


def _role_client(result=None, error=None):
    from unittest.mock import MagicMock
    client = MagicMock()
    client.is_available.return_value = True
    if error:
        client.generate_json.side_effect = error
    else:
        client.generate_json.return_value = result
    return client


def test_role_rewrite_is_one_call_and_maps_results():
    from app.analysis.rewriter import LLMRewriter
    from app.llm.schemas import RoleBulletRewrite, RoleRewriteResult
    resume, evidence, job, plan = _role_setup()
    result = RoleRewriteResult(bullets=[
        RoleBulletRewrite(bullet_id="b1", rewritten="Developed LightGBM fraud models in Python.",
                          keywords_used=["LightGBM", "Python", "PyTorch"]),
        RoleBulletRewrite(bullet_id="b1", rewritten="duplicate, ignored"),
        RoleBulletRewrite(bullet_id="zzz", rewritten="unknown id, ignored"),
    ])
    client = _role_client()
    client.generate_json.side_effect = [result, RoleRewriteResult(bullets=[])]  # the follow-up returns nothing too
    proposals = {p.target_semantic_id: p for p in LLMRewriter(client).execute_plan(resume, plan, evidence, job)}
    assert client.generate_json.call_count == 2  # the role, then one follow-up for skipped b2
    assert set(proposals) == {"b1", "b2"}  # b3 is not relevant, so not sent
    assert proposals["b1"].status == "ok" and proposals["b1"].proposed_text.startswith("Developed")
    assert "PyTorch" not in proposals["b1"].rationale  # only allowed keywords are reported
    assert proposals["b2"].status == "llm_error" and "no rewrite" in proposals["b2"].error
    assert proposals["b2"].proposed_text == "Built Spark pipelines for feature data."


def test_role_rewrite_failure_is_visible_per_bullet():
    from app.analysis.rewriter import LLMRewriter
    resume, evidence, job, plan = _role_setup()
    proposals = LLMRewriter(_role_client(error=RuntimeError("429 rate limited"))).execute_plan(
        resume, plan, evidence, job)
    assert {p.status for p in proposals} == {"llm_error"}
    assert all("429" in p.error and p.proposed_text == p.original_text for p in proposals)


def test_role_rewrite_unchanged_text_is_marked_unchanged():
    from app.analysis.rewriter import LLMRewriter
    from app.llm.schemas import RoleBulletRewrite, RoleRewriteResult
    resume, evidence, job, plan = _role_setup()
    result = RoleRewriteResult(bullets=[RoleBulletRewrite(bullet_id="b2", rewritten="Built Spark pipelines for feature data.")])
    proposals = {p.target_semantic_id: p for p in LLMRewriter(_role_client(result)).execute_plan(resume, plan, evidence, job)}
    assert proposals["b2"].status == "unchanged"


def test_punctuation_only_change_is_unchanged():
    from app.analysis.rewriter import LLMRewriter
    from app.llm.schemas import RoleBulletRewrite, RoleRewriteResult
    resume, evidence, job, plan = _role_setup()
    result = RoleRewriteResult(bullets=[RoleBulletRewrite(bullet_id="b2", rewritten="built Spark pipelines for feature data. ")])
    proposals = {p.target_semantic_id: p for p in LLMRewriter(_role_client(result)).execute_plan(resume, plan, evidence, job)}
    assert proposals["b2"].status == "unchanged"


def test_skipped_bullets_get_one_follow_up_call():
    from unittest.mock import MagicMock
    from app.analysis.rewriter import LLMRewriter
    from app.llm.schemas import RoleBulletRewrite, RoleRewriteResult
    resume, evidence, job, plan = _role_setup()
    client = _role_client()
    client.generate_json.side_effect = [
        RoleRewriteResult(bullets=[RoleBulletRewrite(bullet_id="b1", rewritten="Developed LightGBM fraud models in Python.")]),
        RoleRewriteResult(bullets=[RoleBulletRewrite(bullet_id="b2", rewritten="Engineered Spark feature pipelines.")]),
    ]
    proposals = {p.target_semantic_id: p for p in LLMRewriter(client).execute_plan(resume, plan, evidence, job)}
    assert client.generate_json.call_count == 2
    assert "b2" in client.generate_json.call_args_list[1].kwargs["messages"][1]["content"]
    assert "b1" not in client.generate_json.call_args_list[1].kwargs["messages"][1]["content"]
    assert proposals["b1"].status == proposals["b2"].status == "ok"


def test_breaks_bullet_rules():
    from app.analysis.rewriter import breaks_bullet_rules
    assert breaks_bullet_rules("Built a robust pipeline.")
    assert breaks_bullet_rules(" ".join(["word"] * 29))
    assert not breaks_bullet_rules("Built Spark pipelines for feature data.")


def test_unchanged_bullet_breaking_rules_gets_follow_up():
    from app.analysis.rewriter import LLMRewriter
    from app.domain.resume import ResumeBullet
    from app.llm.schemas import RoleBulletRewrite, RoleRewriteResult
    resume, evidence, job, plan = _role_setup()
    wordy = "Built robust and seamless Spark pipelines for feature data."
    resume.experience[0].bullets[1] = ResumeBullet(id="b2", text=wordy)
    client = _role_client()
    client.generate_json.side_effect = [
        RoleRewriteResult(bullets=[
            RoleBulletRewrite(bullet_id="b1", rewritten="Built LightGBM models in Python for fraud."),  # fine as is
            RoleBulletRewrite(bullet_id="b2", rewritten=wordy),  # kept despite filler words
        ]),
        RoleRewriteResult(bullets=[RoleBulletRewrite(bullet_id="b2", rewritten="Built Spark feature pipelines.")]),
    ]
    proposals = {p.target_semantic_id: p for p in LLMRewriter(client).execute_plan(resume, plan, evidence, job)}
    assert client.generate_json.call_count == 2
    retry_prompt = client.generate_json.call_args_list[1].kwargs["messages"][1]["content"]
    assert "b2" in retry_prompt and "b1" not in retry_prompt and "must not be returned unchanged" in retry_prompt
    assert proposals["b1"].status == "unchanged"
    assert proposals["b2"].status == "ok" and proposals["b2"].proposed_text == "Built Spark feature pipelines."


def test_retry_that_stays_unchanged_keeps_first_result():
    from app.analysis.rewriter import LLMRewriter
    from app.domain.resume import ResumeBullet
    from app.llm.schemas import RoleBulletRewrite, RoleRewriteResult
    resume, evidence, job, plan = _role_setup()
    wordy = "Built robust Spark pipelines for feature data."
    resume.experience[0].bullets[1] = ResumeBullet(id="b2", text=wordy)
    client = _role_client()
    client.generate_json.side_effect = [
        RoleRewriteResult(bullets=[
            RoleBulletRewrite(bullet_id="b1", rewritten="Developed LightGBM fraud models in Python."),
            RoleBulletRewrite(bullet_id="b2", rewritten=wordy),
        ]),
        RoleRewriteResult(bullets=[RoleBulletRewrite(bullet_id="b2", rewritten=wordy)]),
    ]
    proposals = {p.target_semantic_id: p for p in LLMRewriter(client).execute_plan(resume, plan, evidence, job)}
    assert client.generate_json.call_count == 2  # never more than one follow-up
    assert proposals["b2"].status == "unchanged" and proposals["b2"].error is None

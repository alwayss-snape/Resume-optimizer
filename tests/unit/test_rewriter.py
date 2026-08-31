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


@patch("ollama.Client")
def test_suggest_for_missing_requirement_returns_labeled_example(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.list.return_value = {"models": [{"name": "qwen3:4b"}]}
    mock_inst.chat.return_value = {
        "message": {
            "content": (
                '{"suggested_phrasing": "Configured Loan Origination Systems '
                '(Mortgage Cadence) for a fintech implementation team.", '
                '"keywords": ["Loan Origination Systems", "Mortgage Cadence"]}'
            )
        },
    }
    mock_ollama.return_value = mock_inst

    client = LLMClient(model="qwen3:4b", provider="ollama")
    rewriter = LLMRewriter(llm_client=client)

    suggestion = rewriter.suggest_for_missing_requirement(
        "Familiarity with Loan Origination Systems (LOS), especially Mortgage Cadence.",
        jd_keywords=["Loan Origination Systems", "Mortgage Cadence"],
    )

    assert suggestion is not None
    assert "Mortgage Cadence" in suggestion.suggested_phrasing
    assert suggestion.requirement_text.startswith("Familiarity with Loan Origination Systems")


def test_suggest_for_missing_requirement_none_without_llm():
    rewriter = LLMRewriter(llm_client=None)
    assert rewriter.suggest_for_missing_requirement("Some requirement") is None


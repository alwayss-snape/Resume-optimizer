"""Summary tailoring (P1.5) and years of experience from dates."""
from datetime import date
from unittest.mock import MagicMock

import docx

from app.analysis.change_proposal import ChangeProposal
from app.analysis.experience import parse_month, years_of_experience, years_phrase
from app.analysis.keyword_match import KeywordMatcher
from app.analysis.summary_writer import SummaryWriter
from app.domain.evidence import Evidence
from app.domain.job import JobDescription, Requirement
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet, Role
from app.llm.schemas import SummaryResult
from app.services.run_manager import RunManager
from app.services.tailor import TailorService
from app.validation.factual import FactualValidator

TODAY = date(2026, 9, 30)


def _resume():
    return Resume(
        candidate=Candidate(name="Jordan Avery"),
        summary="Data Scientist experienced in forecasting.",
        experience=[
            Experience(id="e1", company="Northwind", title="Senior Data Scientist", start_date="March 2024",
                       end_date="Present",
                       roles=[Role(title="Senior Data Scientist", start_date="March 2024", end_date="Present"),
                              Role(title="Data Scientist", start_date="July 2021", end_date="March 2024")],
                       bullets=[ResumeBullet(id="b1", text="Built Prophet forecasts in Python for 1,200 stores.",
                                             group="Demand Forecasting"),
                                ResumeBullet(id="b2", text="Trained XGBoost churn models.")]),
            Experience(id="e2", company="Blue Harbor", title="Intern", start_date="January 2021",
                       end_date="June 2021", bullets=[ResumeBullet(id="b3", text="Cleaned loan data in SQL.")]),
        ],
    )


def _job():
    req = "Python, XGBoost and SQL for forecasting models"
    return JobDescription(job_title="ML Engineer", keywords=["Python", "XGBoost", "SQL", "Kafka"],
                          requirements=[Requirement(id="r1", text=req)], raw_text=req)


def _evidence(resume):
    ev = [Evidence(id="ev_s", source_type="summary", source_id="blk_s", source_location_id="blk_s", text=resume.summary)]
    for e in resume.experience:
        ev += [Evidence(id=f"ev_{b.id}", source_type="experience", source_id=b.id, text=f"{e.company}: {b.text}")
               for b in e.bullets]
    return ev


def test_years_merge_overlaps_and_parse_formats():
    assert parse_month("Aug. 2024", is_end=False, today=TODAY) == (2024, 8)
    assert parse_month("2018", is_end=True, today=TODAY) == (2018, 12)
    assert parse_month("Present", is_end=True, today=TODAY) == (2026, 9)
    # Jan 2021 - Sep 2026 without gaps: the promotion's roles overlap at March 2024.
    assert years_of_experience(_resume(), TODAY) == round((6 + 63) / 12, 1)
    assert (years_phrase(0.5), years_phrase(1.2), years_phrase(5.8)) == (None, "1 year", "5+ years")


def test_facts_are_decided_in_code():
    resume = _resume()
    facts = SummaryWriter.facts(resume, KeywordMatcher().match(_job(), resume), TODAY)
    assert facts["title"] == "Senior Data Scientist" and facts["years"] == "5+ years"
    assert set(facts["skills"]) == {"Python", "XGBoost", "SQL"}  # Kafka isn't in the resume
    assert facts["results"] == ["Built Prophet forecasts in Python for 1,200 stores."]
    assert facts["projects"] == ["Demand Forecasting"]


def _writer(summary, skills=("Python",)):
    llm = MagicMock()
    llm.is_available.return_value = True
    llm.generate_json.return_value = SummaryResult(summary=summary, skills_used=list(skills))
    return SummaryWriter(llm), llm


def test_propose_returns_a_summary_proposal():
    resume = _resume()
    writer, llm = _writer("Senior Data Scientist with 5+ years in forecasting, using Python, XGBoost and SQL; "
                          "built Prophet forecasts for 1,200 stores.", skills=["Python", "Kafka"])
    prop = writer.propose(resume, _job(), KeywordMatcher().match(_job(), resume), _evidence(resume), TODAY)
    assert llm.generate_json.call_count == 1
    assert prop.kind == "summary" and prop.status == "ok" and prop.allowed_facts[0] == "5+ years"
    assert "Senior Data Scientist" in prop.allowed_facts and "Demand Forecasting" in prop.allowed_facts
    assert "Kafka" not in prop.rationale and "Python" in prop.rationale
    assert "5+ years" in llm.generate_json.call_args.kwargs["messages"][1]["content"]


def test_overlong_summary_is_not_proposed():
    resume = _resume()
    writer, _ = _writer("word " * 80)
    prop = writer.propose(resume, _job(), KeywordMatcher().match(_job(), resume), _evidence(resume), TODAY)
    assert prop.status == "llm_error" and "too long" in prop.error


def _summary_prop(text):
    return ChangeProposal(target_semantic_id="summary", kind="summary", original_text=_resume().summary,
                          proposed_text=text, allowed_facts=["5+ years", "Senior Data Scientist"])


def test_summary_validation_allows_computed_years_and_resume_facts():
    ev = _evidence(_resume())
    ok = FactualValidator().validate_proposal(_summary_prop(
        "Senior Data Scientist with 5+ years; built Prophet forecasts in Python for 1,200 stores."), ev)
    assert ok.verdict == "PASS", ok.warnings


def test_summary_validation_rejects_invented_numbers_and_terms():
    ev = _evidence(_resume())
    bad_num = FactualValidator().validate_proposal(_summary_prop("Data Scientist who cut costs by 40%."), ev)
    bad_term = FactualValidator().validate_proposal(_summary_prop("Data Scientist skilled in Kubernetes."), ev)
    assert bad_num.verdict == bad_term.verdict == "REJECT"


def _service(tmp_path):
    service = TailorService(llm_client=MagicMock(is_available=MagicMock(return_value=False)))
    service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    return service


def test_tailor_applies_summary_in_template_and_preserve_modes(tmp_path):
    new = "Senior Backend Engineer with 6+ years building Python and FastAPI services."
    for mode in ("ATS_DEFAULT", "PRESERVE"):
        service = _service(tmp_path)
        prop = ChangeProposal(target_semantic_id="summary", target_source_location_id="summary", kind="summary",
                              original_text="x", proposed_text=new, user_edited=True).model_dump()
        result = service.tailor_resume("tests/fixtures/resumes/sample.docx", "Requirements:\n- Python.",
                                       str(tmp_path / mode), mode=mode, preapproved_proposals=[prop])
        texts = [p.text for p in docx.Document(result["docx"]).paragraphs]
        assert new in texts, mode
        assert not any(t.startswith("Senior Software Engineer with 6+ years") for t in texts), mode


def test_capital_at_start_of_any_sentence_is_not_a_proper_noun():
    ev = _evidence(_resume())
    result = FactualValidator().validate_proposal(_summary_prop(
        "Senior Data Scientist with 5+ years. Builds XGBoost churn models. Cut costs for 1,200 stores."), ev)
    assert result.verdict == "PASS", result.warnings


def test_years_follow_the_resumes_own_claim_and_titles_are_sane():
    """P8.10: the summary repeats the years the resume states (computed
    only when it states none), never prints a misread title, keeps the
    user's own summary unless they choose the new one, and lists licences
    apart from tools."""
    from app.analysis.summary_writer import SummaryWriter
    resume = _resume()
    resume.summary = "Account executive with 7 years of B2B SaaS sales."
    assert SummaryWriter.years_claim(resume) == "7 years"
    assert SummaryWriter.facts(resume, KeywordMatcher().match(_job(), resume), TODAY)["years"] == "7 years"
    assert not SummaryWriter.sane_title("03/") and not SummaryWriter.sane_title("06/2019 - 02/2021")
    assert SummaryWriter.sane_title("Registered Nurse - Step-Down Unit")
    writer, _llm = _writer("Senior Data Scientist with 7 years in forecasting, using Python and SQL.")
    prop = writer.propose(resume, _job(), KeywordMatcher().match(_job(), resume), _evidence(resume), TODAY)
    assert prop.opt_in is True  # the resume has its own summary

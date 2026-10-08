"""P11.13: a summary's kind of work must be a phrase the resume uses, not one shared word."""
from app.analysis.change_proposal import ChangeProposal
from app.domain.evidence import Evidence
from app.validation.factual import FactualValidator

LINES = [
    "Implemented model selection and hyperparameter optimization across 20 candidate models.",
    "Built demand forecasting models for 1,200 stores in Python.",
    "Deployed an end-to-end scoring pipeline on Kubernetes.",
]


def _evidence():
    return [Evidence(id=f"ev{i}", source_type="experience", source_id=f"b{i}", text=t) for i, t in enumerate(LINES)]


def _check(text):
    prop = ChangeProposal(target_semantic_id="summary", kind="summary", original_text="Data Scientist.",
                          proposed_text=text, allowed_facts=[])
    return FactualValidator().validate_proposal(prop, _evidence())


def test_optimization_models_from_hyperparameter_optimization_is_flagged():
    result = _check("Data Scientist who builds optimization models.")
    assert result.verdict == "NEEDS_CONFIRM"
    assert any("'optimization models'" in w and "hyperparameter optimization" in w for w in result.warnings)


def test_a_phrase_the_resume_uses_passes_in_any_tense():
    assert _check("Data Scientist who builds demand forecasting models in Python.").verdict == "PASS"
    assert _check("Data Scientist experienced in hyperparameter optimization and model selection.").verdict == "PASS"
    assert _check("Data Scientist who deploys end-to-end scoring pipelines.").verdict == "PASS"


def test_one_word_claims_and_text_without_a_work_verb_are_left_to_the_word_check():
    assert _check("Data Scientist who builds models.").verdict == "PASS"
    assert _check("Data Scientist focused on forecasting, with Python and Kubernetes.").verdict == "PASS"


def test_each_claim_after_and_is_checked_on_its_own():
    result = _check("Data Scientist who builds and deploys optimization models.")
    assert result.verdict == "NEEDS_CONFIRM"


def _check_with(lines, text):
    ev = [Evidence(id=f"ev{i}", source_type="experience", source_id=f"b{i}", text=t) for i, t in enumerate(lines)]
    prop = ChangeProposal(target_semantic_id="summary", kind="summary", original_text="Engineer.",
                          proposed_text=text, allowed_facts=[])
    return FactualValidator().validate_proposal(prop, ev)


def test_filler_words_between_do_not_make_a_phrase_review_p1113():
    for line in ("Implemented hyperparameter optimization across 20 models.",
                 "Ran hyperparameter optimization over 300 models.",
                 "Tuned hyperparameter optimization for models in production."):
        result = _check_with([line], "Engineer who builds optimization models.")
        assert result.verdict == "NEEDS_CONFIRM", line
        assert "'hyperparameter optimization'" in " ".join(result.warnings)


def test_ordinary_true_summaries_pass_review_p1113():
    assert _check_with(["Built dashboards in Power BI for sales."], "Analyst who builds Power BI dashboards.").verdict == "PASS"
    assert _check_with(["Built machine learning models to predict churn."], "Engineer who builds ML models.").verdict == "PASS"
    assert _check_with(["Built REST APIs in Go."], "Experienced backend engineer who develops REST APIs.").verdict == "PASS"
    assert _check_with(["Built REST APIs in Go."], "Engineer experienced in REST APIs.").verdict == "PASS"

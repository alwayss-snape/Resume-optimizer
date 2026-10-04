"""JD analysis v2 (P1.1): title/company without labels, whole-line
requirements, "Nice To Have, But Not Required" = preferred, one structured
LLM call whose every string is checked against the JD."""
from app.analysis.jd_analyzer import JDAnalyzer
from app.llm.schemas import JDAnalysisResult, JDRequirementLine

JD = open("tests/fixtures/jds/replica_layout_jd.txt", encoding="utf-8").read()
REQUIREMENT_LINES = [
    "Design and build ranking and retrieval models for search and recommendations",
    "Own the full model lifecycle: data preparation, training, evaluation, and monitoring",
    "Collaborate with data engineers and product managers to ship models into batch and real-time pipelines",
    "Mentor junior engineers and review code",
    "At least 4-8 years of experience in machine learning or applied data science",
    "Proficient in Python and libraries like PyTorch and XGBoost",
    "Experience with Spark or Snowflake for large-scale data processing",
    "Strong grasp of A/B testing design and analysis",
    "Experience with vector search (e.g., FAISS) is a plus",
    "Experience with Kafka and streaming architectures",
    "Contributions to open-source ML tools",
]
PREFERRED = {
    "Experience with vector search (e.g., FAISS) is a plus",
    "Experience with Kafka and streaming architectures",
    "Contributions to open-source ML tools",
}


class FakeLLM:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def is_available(self):
        return True

    def generate_json(self, messages, schema_model, **kwargs):
        self.calls += 1
        assert schema_model is JDAnalysisResult
        return self.result


def test_heuristic_title_company_seniority_years_without_labels():
    jd = JDAnalyzer(None).analyze(JD)
    assert jd.job_title == "Senior Engineer, Search (L3)"
    assert jd.company == "Contoso Media"
    assert jd.seniority == "senior"
    assert (jd.min_years, jd.max_years) == (4, 8)
    assert jd.analysis_source == "heuristic"


def test_heuristic_whole_lines_no_and_splitting_and_no_intro_or_headings():
    jd = JDAnalyzer(None).analyze(JD)
    assert [r.text for r in jd.requirements] == REQUIREMENT_LINES
    # Every requirement is a verbatim span of the (cleaned) JD the job keeps (P9.5).
    for r in jd.requirements:
        start, end = r.source_spans[0]["start"], r.source_spans[0]["end"]
        assert jd.raw_text[start:end] == r.text


def test_nice_to_have_heading_and_is_a_plus_are_preferred():
    jd = JDAnalyzer(None).analyze(JD)
    assert {r.text for r in jd.requirements if r.priority == "preferred"} == PREFERRED
    assert all(r.criticality == r.priority for r in jd.requirements)


def test_keywords_skip_heading_and_company_words():
    jd = JDAnalyzer(None).analyze(JD)
    lowered = {k.lower() for k in jd.keywords}
    # "A/B testing" (a known multi-word term) replaces the bare "A/B" (P4.2).
    assert {"python", "pytorch", "xgboost", "spark", "snowflake", "a/b testing", "faiss", "kafka"} <= lowered
    assert not lowered & {"what", "will", "contoso", "media", "about"}
    assert jd.keyword_counts["Python"] == 1


def _llm_result(**overrides):
    lines = JDAnalyzer()._reflow_lines(JD)
    base = dict(
        job_title="Senior Engineer, Search (L3)",
        company="Contoso Media",
        seniority="senior",
        min_years=4,
        max_years=8,
        requirement_lines=[JDRequirementLine(index=lines.index(t)) for t in REQUIREMENT_LINES],
        hard_skills=["Python", "PyTorch", "XGBoost", "Spark", "Snowflake", "A/B testing", "FAISS", "Kafka",
                     "Kubernetes"],  # not in the JD: must be dropped
        soft_skills=["Mentor"],
    )
    base.update(overrides)
    return JDAnalysisResult(**base)


def test_llm_path_is_one_call_and_every_value_is_verbatim():
    llm = FakeLLM(_llm_result(job_title="senior engineer, search (l3)"))
    jd = JDAnalyzer(llm).analyze(JD)
    assert llm.calls == 1 and jd.analysis_source == "llm"
    assert jd.job_title == "Senior Engineer, Search (L3)"  # the JD's own spelling
    assert "Kubernetes" not in jd.hard_skills and "Kubernetes" not in jd.keywords
    assert jd.hard_skills[:3] == ["Python", "PyTorch", "XGBoost"]
    assert [r.text for r in jd.requirements] == REQUIREMENT_LINES
    assert {r.text for r in jd.requirements if r.priority == "preferred"} == PREFERRED


def test_llm_invented_title_and_years_are_rejected():
    llm = FakeLLM(_llm_result(job_title="Staff ML Engineer", company="Initech", min_years=10, max_years=None))
    jd = JDAnalyzer(llm).analyze(JD)
    # Falls back to the deterministic reading for anything not in the JD.
    assert jd.job_title == "Senior Engineer, Search (L3)"
    assert jd.company == "Contoso Media"
    assert (jd.min_years, jd.max_years) == (4, 8)


def test_llm_keywords_are_topped_up_from_requirement_lines():
    llm = FakeLLM(_llm_result(hard_skills=["Python"]))
    jd = JDAnalyzer(llm).analyze(JD)
    assert {"Python", "PyTorch", "XGBoost", "A/B testing", "FAISS", "Kafka", "ML"} <= set(jd.keywords)

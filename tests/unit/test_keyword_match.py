"""Keyword-level match rate as the headline score (P1.2)."""
import os

from streamlit.testing.v1 import AppTest

from app.analysis.keyword_match import KeywordMatcher, tokens
from app.domain.job import JobDescription, Requirement
from app.domain.report import TailoringReport
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet, Role


def _resume(bullets, skills=None, titles=("Data Scientist",), headline=None):
    return Resume(
        candidate=Candidate(name="A", headline=headline),
        summary="Data scientist working on machine learning.",
        experience=[Experience(id="e1", company="Acme", title=titles[0],
                               roles=[Role(title=t) for t in titles] if len(titles) > 1 else [],
                               bullets=[ResumeBullet(id=f"b{i}", text=t) for i, t in enumerate(bullets)])],
        skills=skills or {},
    )


def _job(keywords, required_lines=None, preferred_lines=None, title=None, soft=None):
    reqs = [Requirement(id=f"r{i}", text=t, priority="required") for i, t in enumerate(required_lines or [])]
    reqs += [Requirement(id=f"p{i}", text=t, priority="preferred", criticality="preferred")
             for i, t in enumerate(preferred_lines or [])]
    raw = "\n".join((required_lines or []) + (preferred_lines or []))
    return JobDescription(job_title=title or "Target Role", keywords=keywords, requirements=reqs,
                          soft_skills=soft or [], raw_text=raw)


def _rows(report):
    return {r.keyword: r for r in report.rows}


def test_aliases_plurals_and_implied_terms():
    resume = _resume(["Built feature store pipelines in PySpark for ML models."], skills={"Tools": ["AWS"]})
    job = _job(["machine learning", "feature stores", "Spark", "Amazon Web Services"],
               required_lines=["machine learning, feature stores, Spark, Amazon Web Services"])
    rows = _rows(KeywordMatcher().match(job, resume))
    assert all(rows[k].found for k in rows), {k: r.found for k, r in rows.items()}


def test_whole_tokens_only():
    resume = _resume(["Built React apps and MLflow tracking."])
    job = _job(["R", "ML"], required_lines=["R and ML"])
    rows = _rows(KeywordMatcher().match(job, resume))
    # "R" is not in "React"; the summary does say "machine learning" (= ML).
    assert rows["R"].found is False and rows["ML"].found is True


def test_multi_word_term_within_one_sentence():
    resume = _resume(["Designed systems for product recommendation at scale."])
    job = _job(["recommendation systems"], required_lines=["recommendation systems"])
    assert KeywordMatcher().match(job, resume).rows[0].found


def test_required_keywords_weigh_more_and_rate_is_weighted():
    resume = _resume(["Used Python daily."])
    job = _job(["Python", "Kafka"], required_lines=["Python"], preferred_lines=["Kafka is a plus"])
    report = KeywordMatcher().match(job, resume)
    rows = _rows(report)
    assert (rows["Python"].weight, rows["Kafka"].weight) == (4.5, 3.0)
    assert report.rate == round(100 * 4.5 / 7.5, 1)


def test_perfect_match_is_100_and_empty_is_0():
    resume = _resume(["Python and SQL."])
    assert KeywordMatcher().match(_job(["Python", "SQL"], ["Python and SQL"]), resume).rate == 100.0
    assert KeywordMatcher().match(_job([]), resume).rate == 0.0


def test_title_gets_partial_credit_from_role_titles():
    resume = _resume(["x"], titles=("Data Scientist II", "Data Scientist I"))
    job = _job([], title="Senior Machine Learning Engineer")
    [row] = KeywordMatcher().match(job, resume).rows
    assert row.kind == "title" and row.credit == 0.0
    job = _job([], title="Senior Data Scientist, ML")
    [row] = KeywordMatcher().match(job, resume).rows
    assert row.found and row.credit == round(2 / 4, 2)  # data, scientist of data, scientist, machine, learning


def test_soft_skills_count_less():
    resume = _resume(["Mentored two analysts."])
    job = _job(["Python"], required_lines=["Python"], soft=["mentored"])
    rows = _rows(KeywordMatcher().match(job, resume))
    assert rows["mentored"].kind == "soft" and rows["mentored"].weight < rows["Python"].weight


def test_tokens_normalise_case_alias_and_plural():
    assert tokens("Feature Stores for ML") == ["feature", "store", "for", "machine", "learning"]


def test_analysis_view_shows_keyword_table():
    resume = _resume(["Used Python."])
    report = KeywordMatcher().match(_job(["Python", "Kafka"], ["Python", "Kafka"]), resume)
    at = AppTest.from_file(os.path.abspath("app/ui.py"), default_timeout=60)
    at.session_state["stage"] = "analysis"
    at.session_state["analysis_report"] = TailoringReport(alignment_score=report.rate, keyword_match=report,
                                                          score_components={"evidence_score": 12.0})
    at.run()
    assert not at.exception
    assert at.metric[0].value == "50.0%"
    assert len(at.dataframe) == 1

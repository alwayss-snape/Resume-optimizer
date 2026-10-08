"""P11.3: the role brief, what the job really needs."""
from app.analysis.role_brief import checked_brief, fallback_brief, write_brief
from app.domain.job import JobDescription
from app.domain.resume import Candidate, Resume
from app.llm.schemas import RoleBriefResult

POST = ("We are looking for a Senior Data Scientist to help solve challenging pricing, yield optimization and "
        "inventory management problems. We are particularly interested in people with a strong operations research "
        "or optimization background who enjoy applying analytics to real business decisions at scale.")
JD = JobDescription(raw_text=POST, job_title="Senior Data Scientist", keywords=["Data", "pricing", "operations research"])


def _result(**kw):
    base = {"target_title": "Senior Data Scientist", "positioning": "Applies forecasting and targeting to retail decisions.",
            "competencies": [
                {"name": "Pricing analytics", "kind": "stated", "jd_words": "pricing", "look_for": ["Price", "discount"]},
                {"name": "Demand forecasting", "kind": "inferred", "jd_words": "inventory management",
                 "look_for": ["forecast", "demand"]},
                {"name": "Team leadership", "kind": "inferred", "jd_words": "managing a team of five",  # not in the post
                 "look_for": ["led"]},
            ]}
    base.update(kw)
    return RoleBriefResult(**base)


def test_a_competency_must_rest_on_the_jds_own_words():
    brief = checked_brief(_result(), JD)
    assert [c.name for c in brief.competencies] == ["Pricing analytics", "Demand forecasting"]
    assert brief.competencies[1].kind == "inferred" and brief.competencies[0].look_for == ["price", "discount"]
    assert "price" in brief.terms() and "Demand forecasting" in brief.terms()


def test_a_title_the_jd_doesnt_give_falls_back_to_its_own():
    assert checked_brief(_result(target_title="Chief Pricing Officer"), JD).target_title == "Senior Data Scientist"


def test_nothing_usable_or_no_ai_gives_the_jds_own_skills():
    brief = checked_brief(_result(competencies=[]), JD)
    assert brief.source == "heuristic" and [c.name for c in brief.competencies] == ["pricing", "operations research"]
    assert write_brief(JD, Resume(candidate=Candidate(name="A B")), None).competencies == fallback_brief(JD).competencies


class _BriefLLM:
    def is_available(self):
        return True

    def generate_json(self, messages, schema_model, **kwargs):
        assert schema_model is RoleBriefResult and "Resume overview" in messages[-1]["content"]
        return _result()


def test_the_brief_is_written_with_the_resume_in_view():
    brief = write_brief(JD, Resume(candidate=Candidate(name="A B")), _BriefLLM())
    assert brief.source == "llm" and brief.positioning.startswith("Applies forecasting")


def test_projects_are_chosen_to_cover_different_competencies():
    """P11.4: two forecasting projects and one pricing project; the job needs both."""
    from app.analysis.project_select import select_projects
    from app.domain.resume import Experience, ResumeBullet
    from app.domain.tailoring import TailoringAction
    groups = {"Forecast Platform": "Built demand forecast models for weekly sales.",
              "Forecast Tuning": "Tuned demand forecast models with hyperparameter search.",
              "Fee Pricing": "Set the membership fee price tiers and discount levels.",
              "Label Checks": "Checked product labels with OCR."}
    exp = Experience(id="e1", company="Acme", title="DS", start_date="Jan 2020", end_date="Mar 2021", bullets=[
        ResumeBullet(id=f"b{i}", text=t, group=g) for i, (g, t) in enumerate(groups.items())])
    resume = Resume(candidate=Candidate(name="A B"), experience=[
        Experience(id="e0", company="Now", title="DS", start_date="Apr 2021", end_date="Present"), exp])
    brief = checked_brief(_result(), JD)
    vec = lambda t: [1.0, 0.0] if ("forecast" in t.lower() or "demand" in t.lower()) else \
        ([0.0, 1.0] if ("pric" in t.lower() or "discount" in t.lower()) else [0.1, 0.1])
    actions = [TailoringAction(action="REWRITE", source_id=b.id, relevance=0.2) for b in exp.bullets]
    choices = select_projects(resume, actions, JD, embedder=lambda ts: [vec(t) for t in ts], brief=brief)
    kept = [c.name for c in choices if c.chosen]
    assert kept == ["Forecast Platform", "Fee Pricing"]  # not both forecasting projects
    pricing = next(c for c in choices if c.name == "Fee Pricing")
    assert pricing.covers[0] == "Pricing analytics" and pricing.reason == "Nearest to Pricing analytics"  # no AI map: "nearest"
    tuning = next(c for c in choices if c.name == "Forecast Tuning")
    assert tuning.reason.startswith("Covered better by the projects kept")



class _MapLLM:
    """Links projects to competencies; one quote is made up."""
    def is_available(self):
        return True

    def generate_json(self, messages, schema_model, **kwargs):
        from app.llm.schemas import ProjectEvidenceResult
        assert schema_model is ProjectEvidenceResult
        return ProjectEvidenceResult(projects=[
            {"project": 0, "shows": [{"competency": "Demand forecasting", "quote": "demand forecast models for weekly sales"}]},
            {"project": 2, "shows": [{"competency": "Pricing analytics", "quote": "membership fee price tiers"},
                                     {"competency": "Demand forecasting", "quote": "forecast holiday demand by store"}]},
            {"project": 3, "shows": [{"competency": "Pricing analytics", "quote": "Checked product labels"}]},
        ])


def test_the_ai_map_keeps_only_links_with_the_projects_own_words():
    from app.analysis.project_select import select_projects
    from app.analysis.role_brief import map_projects
    from app.domain.resume import Experience, ResumeBullet
    from app.domain.tailoring import TailoringAction
    groups = {"Forecast Platform": "Built demand forecast models for weekly sales.",
              "Forecast Tuning": "Tuned demand forecast models with hyperparameter search.",
              "Fee Pricing": "Set the membership fee price tiers and discount levels.",
              "Label Checks": "Checked product labels with OCR."}
    exp = Experience(id="e1", company="Acme", title="DS", start_date="Jan 2020", end_date="Mar 2021", bullets=[
        ResumeBullet(id=f"b{i}", text=t, group=g) for i, (g, t) in enumerate(groups.items())])
    resume = Resume(candidate=Candidate(name="A B"), experience=[
        Experience(id="e0", company="Now", title="DS", start_date="Apr 2021", end_date="Present"), exp])
    brief = map_projects(checked_brief(_result(), JD), resume, {}, _MapLLM())
    ev = brief.project_evidence
    assert ev["e1::Forecast Platform"] == [{"competency": "Demand forecasting", "quote": "demand forecast models for weekly sales"}]
    assert ev["e1::Fee Pricing"] == [{"competency": "Pricing analytics", "quote": "membership fee price tiers"}]  # made-up quote dropped
    assert ev["e1::Label Checks"] == [{"competency": "Pricing analytics", "quote": "Checked product labels"}]  # real words, weak link
    actions = [TailoringAction(action="REWRITE", source_id=b.id, relevance=0.2) for b in exp.bullets]
    choices = {c.name: c for c in select_projects(resume, actions, JD, brief=brief)}
    assert choices["Fee Pricing"].reason == "Shows Pricing analytics: \u201cmembership fee price tiers\u201d"
    assert choices["Forecast Tuning"].reason == "Shows none of what this job needs"

"""P2.6: deterministic content checks on the finished resume."""
from datetime import date

from app.domain.resume import Candidate, Experience, Project, Resume, ResumeBullet, Role
from app.validation.content_lint import lint

TODAY = date(2026, 9, 30)


def _job(company, bullets, start="Jan 2022", end="Present", roles=None):
    return Experience(id=company, company=company, title="Engineer",
                      roles=roles or [Role(title="Engineer", start_date=start, end_date=end)],
                      bullets=[ResumeBullet(id=f"{company}{i}", text=t) for i, t in enumerate(bullets)])


GOOD = ["Cut API latency by 40% by caching hot queries in Redis.",
        "Migrated 12 services to Kubernetes with zero downtime.",
        "Designed the billing schema used by 3 product teams."]


def _checks(resume):
    return [i.check for i in lint(resume, TODAY).issues]


def test_clean_resume_has_no_issues():
    resume = Resume(candidate=Candidate(name="A"), experience=[_job("Acme", GOOD)])
    report = lint(resume, TODAY)
    assert report.issues == [] and report.bullets == 3 and report.metric_share == 1.0


def test_flags_pronouns_buzzwords_length_and_gerunds():
    bullets = ["I built a robust and seamless pipeline for the team in Python.",
               "Working on dashboards for 5 regions.",
               "Did stuff.",
               "Shipped " + " ".join(["features"] * 30) + " in 2 weeks."]
    checks = _checks(Resume(candidate=Candidate(name="A"), experience=[_job("Acme", bullets)]))
    assert {"pronoun", "buzzword", "tense", "length"} <= set(checks)
    assert checks.count("length") == 2  # too short and too long


def test_past_role_present_tense_and_repeated_verbs():
    older = _job("Initech", ["Builds reports for 4 teams.", "Builds dashboards for 2 teams."],
                 start="Jan 2018", end="Dec 2021")
    checks = _checks(Resume(candidate=Candidate(name="A"), experience=[_job("Acme", GOOD), older]))
    assert checks.count("tense") == 2 and "repeated_verb" in checks


def test_bullets_per_role_and_promotions():
    many = [f"Delivered feature {i} for 2 clients." for i in range(8)]
    assert "bullets_per_role" in _checks(Resume(candidate=Candidate(name="A"), experience=[_job("Acme", many)]))
    promoted = _job("Acme", many, roles=[Role(title="Senior", start_date="Jan 2024", end_date="Present"),
                                         Role(title="Engineer", start_date="Jan 2022", end_date="Dec 2023")])
    assert "bullets_per_role" not in _checks(Resume(candidate=Candidate(name="A"), experience=[promoted]))
    assert "bullets_per_role" in _checks(Resume(candidate=Candidate(name="A"), experience=[_job("Acme", GOOD[:1])]))


def test_dates():
    jobs = [_job("Acme", GOOD, start="Jan 2027"), _job("Initech", GOOD[:2], start="Jan 2020", end="Jan 2019"),
            _job("Globex", GOOD[:2], start=None, end=None)]
    issues = [i.message for i in lint(Resume(candidate=Candidate(name="A"), experience=jobs), TODAY).issues
              if i.check == "dates"]
    assert any("future" in m for m in issues)
    assert any("before the start" in m for m in issues)
    assert any("No start date" in m for m in issues)


def test_metric_share_counts_projects_too():
    resume = Resume(candidate=Candidate(name="A"), experience=[_job("Acme", GOOD)],
                    projects=[Project(id="p", name="Tool", bullets=[
                        ResumeBullet(id=f"p{i}", text="Wrote a command line tool for log search.") for i in range(8)])])
    report = lint(resume, TODAY)
    assert report.bullets == 11 and report.bullets_with_metrics == 3
    assert "metrics" in [i.check for i in report.issues]

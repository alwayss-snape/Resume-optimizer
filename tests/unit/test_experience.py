"""P2.3: years of experience (overlaps merged) -> 1 or 2 target pages."""
from datetime import date

from app.analysis.experience import target_pages, years_of_experience
from app.domain.resume import Candidate, Experience, Resume, Role

TODAY = date(2026, 9, 30)


def _resume(*roles):
    return Resume(candidate=Candidate(name="A"), experience=[
        Experience(id=f"e{i}", company=f"Co{i}", title=r.title, roles=[r]) for i, r in enumerate(roles)])


def test_under_eight_years_is_one_page():
    resume = _resume(Role(title="Engineer", start_date="Jan 2020", end_date="Present"))
    assert years_of_experience(resume, TODAY) < 8
    assert target_pages(resume, TODAY) == 1


def test_eight_years_or_more_is_two_pages():
    resume = _resume(Role(title="Senior", start_date="Jan 2021", end_date="Present"),
                     Role(title="Engineer", start_date="Jan 2015", end_date="Dec 2020"))
    assert years_of_experience(resume, TODAY) >= 8
    assert target_pages(resume, TODAY) == 2


def test_overlapping_roles_are_not_double_counted():
    # Two concurrent 5-year jobs are 5 years, not 10.
    resume = _resume(Role(title="A", start_date="Jan 2020", end_date="Dec 2024"),
                     Role(title="B", start_date="Jan 2020", end_date="Dec 2024"))
    assert years_of_experience(resume, TODAY) == 5.0
    assert target_pages(resume, TODAY) == 1


def test_no_dated_roles_is_one_page():
    assert target_pages(Resume(candidate=Candidate(name="A")), TODAY) == 1

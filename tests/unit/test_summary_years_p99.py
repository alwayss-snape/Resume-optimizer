"""P9.9: the summary reuses the years the resume itself states ("3.6 years"),
not a figure computed from the role dates ("4+ years")."""
import pytest

from app.analysis.summary_writer import SummaryWriter
from app.domain.resume import Candidate, Resume


@pytest.mark.parametrize("summary, headline, expected", [
    ("Data scientist with 3.6 years of experience building ML systems", "", "3.6 years"),
    ("Analyst with 3.6 yrs experience", "", "3.6 years"),
    ("", "3.6 years in ML", "3.6 years"),
    ("Engineer with 3 years 7 months of experience", "", "3 years 7 months"),
    ("Engineer with 3 years and 7 months of experience", "", "3 years 7 months"),
    ("5+ yrs in sales", "", "5+ years"),
    ("5+ years 2 months of experience", "", "5+ years"),  # review F3
    ("3 years of Python, 6 years of experience", "", "6 years"),  # the career claim wins
    ("Built dashboards for 12 teams", "", None),  # nothing stated: the computed figure is used
])
def test_summary_years_reuse_the_resumes_own_figure(summary, headline, expected):
    resume = Resume(candidate=Candidate(name="A", headline=headline), summary=summary)
    assert SummaryWriter.years_claim(resume, 4.2) == expected


def test_summary_years_far_below_the_dated_roles_are_not_a_career_claim():
    resume = Resume(candidate=Candidate(name="A"), summary="2 years of Python")
    assert SummaryWriter.years_claim(resume, 10.0) is None

"""P8.6: date formats from outside the US tech norm."""
from datetime import date

import pytest

from app.analysis.experience import future_dates, is_ongoing, parse_month, years_of_experience
from app.analysis.resume_normalizer import ResumeNormalizer
from app.domain.resume import Candidate, Experience, Resume
from app.rendering.layout import date_range, format_date

TODAY = date(2026, 10, 3)


@pytest.mark.parametrize("line, start, end", [
    ("Analyst | Summer 2019 – Fall 2020", "Summer 2019", "Fall 2020"),
    ("Analyst | 03/2019 – 06/2021", "03/2019", "06/2021"),
    ("Analyst | 01/09/2019 – 31/08/2023", "01/09/2019", "31/08/2023"),
    ("Analyst | July 2018 – Till Date", "July 2018", "Till Date"),
    ("Analyst | 2020 – Ongoing", "2020", "Ongoing"),
    ("Analyst | 2019-03 – 2021-05", "2019-03", "2021-05"),
    ("Analyst | Jan '19 – Mar '21", "Jan '19", "Mar '21"),
    ("Projektmanager, Siemens AG | 01/2019 – heute", "01/2019", "heute"),
    ("Enfermera | 2020 – Actualidad", "2020", "Actualidad"),
    ("Curriculum Writer | Texas Education Agency | Summer 2021", "Summer 2021", None),
    ("Analyst | 2018", "2018", None),
])
def test_date_ranges(line, start, end):
    _title, got_start, got_end = ResumeNormalizer()._parse_title_and_dates(line)
    assert (got_start, got_end) == (start, end)


@pytest.mark.parametrize("value, ym", [
    ("Summer 2021", (2021, 6)), ("Fall 2020", (2020, 9)), ("31/08/2023", (2023, 8)), ("2019-03", (2019, 3)),
    ("Jan '19", (2019, 1)), ("Till Date", (2026, 10)), ("heute", (2026, 10)), ("Actualidad", (2026, 10)),
])
def test_parse_month(value, ym):
    assert parse_month(value, is_end=False, today=TODAY) == ym


def test_formatting_and_ongoing():
    assert format_date("2019-03") == "Mar 2019"
    assert format_date("Jan '19") == "Jan 2019"
    assert format_date("31/08/2023") == "Aug 2023"
    assert format_date("Summer 2021") == "Summer 2021"
    assert format_date("Till Date") == "Present"
    assert date_range("Summer 2021", None) == "Summer 2021"
    assert is_ongoing("to date") and is_ongoing("Heute")


def test_years_from_eu_dates_and_future_flag():
    resume = Resume(candidate=Candidate(name="Z"), experience=[
        Experience(id="e1", company="Groupe SEB", title="Analyst", start_date="01/09/2019", end_date="31/08/2023"),
        Experience(id="e2", company="Acme", title="Lead", start_date="05/2027", end_date="Present"),
    ])
    assert years_of_experience(Resume(candidate=Candidate(name="Z"), experience=resume.experience[:1]),
                               TODAY) == 4.0
    assert future_dates(resume, TODAY) == ["Lead at Acme starts in the future (05/2027)"]

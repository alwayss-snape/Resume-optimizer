"""P11.18 (owner's run, 2026-10-09): "Company<tab>dates" then "Title<tab>City" is one job, not a date in Location."""
from app.services.tailor import TailorService

RESUME = ("Jordan Avery\njordan@example.com\n\nEXPERIENCE\n"
          "Northwind Grocers\tMar 2026 – Present\n"
          "Machine Learning Engineer\tPune, India\n"
          "- Built a route planner for 40 depots.\n"
          "Fabrikam – A Contoso Group Company\tAug 2022 – Mar 2026\n"
          "Data Scientist II (Aug 2024 – Mar 2026) | Data Scientist I (Aug 2022 – Aug 2024)\tPune, India\n"
          "- Built churn models for 3 brands.\n\n"
          "EDUCATION\nB.Tech, Computer Science — Lakeside University\t2018 – 2022\n")


def _parse(tmp_path, text=RESUME):
    path = tmp_path / "r.txt"
    path.write_text(text, encoding="utf-8")
    return TailorService(llm_client=None).parse_resume(str(path))[1].resume


def test_company_first_headers_and_promotions_on_one_line(tmp_path):
    jobs = [(e.company, e.location, [(r.title, r.start_date, r.end_date) for r in e.all_roles()], len(e.bullets))
            for e in _parse(tmp_path).experience]
    assert jobs == [
        ("Northwind Grocers", "Pune, India", [("Machine Learning Engineer", "Mar 2026", "Present")], 1),
        ("Fabrikam – A Contoso Group Company", "Pune, India",
         [("Data Scientist II", "Aug 2024", "Mar 2026"), ("Data Scientist I", "Aug 2022", "Aug 2024")], 1)]


def test_title_first_headers_are_unchanged(tmp_path):
    text = ("Jordan Avery\njordan@example.com\n\nEXPERIENCE\n"
            "Machine Learning Engineer\tMar 2026 – Present\nNorthwind Grocers\tPune, India\n"
            "- Built a route planner for 40 depots.\n")
    [job] = _parse(tmp_path, text).experience
    assert (job.company, job.title, job.location, job.start_date) == (
        "Northwind Grocers", "Machine Learning Engineer", "Pune, India", "Mar 2026")


def test_review_p1118_remote_or_a_bare_city_is_a_location(tmp_path):
    for place in ("Remote", "Bangalore", "Pune, India (Hybrid)"):
        text = ("Jordan Avery\njordan@example.com\n\nEXPERIENCE\n"
                f"Northwind Grocers\tMar 2020 – Present\nSenior Analyst (Mar 2022 – Present) | Analyst (Mar 2020 – Mar 2022)\t{place}\n"
                "- Built weekly sales reports.\n")
        [job] = _parse(tmp_path, text).experience
        assert (job.company, job.location) == ("Northwind Grocers", place)
        assert [(r.title, r.start_date) for r in job.all_roles()] == [("Senior Analyst", "Mar 2022"), ("Analyst", "Mar 2020")]


def test_review_p1118_promotions_without_their_own_dates_are_not_given_the_jobs(tmp_path):
    text = ("Jordan Avery\njordan@example.com\n\nEXPERIENCE\n"
            "Northwind Grocers\tMar 2020 – Present\nSenior Analyst | Analyst\tPune, India\n- Built weekly sales reports.\n")
    [job] = _parse(tmp_path, text).experience
    assert (job.company, job.location) == ("Northwind Grocers", "Pune, India")
    assert [(r.title, r.start_date, r.end_date) for r in job.all_roles()] == [("Senior Analyst | Analyst", "Mar 2020", "Present")]

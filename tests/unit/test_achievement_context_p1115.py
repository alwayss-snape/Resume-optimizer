"""P11.15: achievements gain where and when, from evidence only, as a proposal."""
from app.analysis.achievement_context import achievement_proposals, added_context, context_for, with_context
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet, Role


def _resume(achievements):
    now = Experience(id="e1", company="Northwind Grocers", title="ML Engineer", start_date="Mar 2023",
                     end_date="Present", bullets=[
                         ResumeBullet(id="b1", text="Built a route planner for 40 depots.", group="Route Pilot"),
                         ResumeBullet(id="b2", text="Cut empty miles in 2024 across the pilot depots.", group="Route Pilot"),
                         ResumeBullet(id="b3", text="Matched shelf labels with OCR.", group="Label Checks"),
                         ResumeBullet(id="b4", text="Labelled 3 years of scans.", group="Label Checks")])
    old = Experience(id="e2", company="Fabrikam Analytics", title="Analyst", start_date="Jan 2021",
                     end_date="Nov 2021", roles=[Role(title="Analyst", start_date="Jan 2021", end_date="Nov 2021")],
                     bullets=[ResumeBullet(id="b5", text="Built churn dashboards.")])
    return Resume(candidate=Candidate(name="A B"), experience=[now, old], achievements=achievements)


def test_a_project_named_in_an_achievement_gives_its_company_and_its_one_year():
    r = _resume(["Won an internal hackathon with Route Pilot."])
    assert context_for(r.achievements[0], r, {}) == "Northwind Grocers, 2024"
    [p] = achievement_proposals(r, {})
    assert p.kind == "achievement" and p.target_semantic_id == "achievement::0"
    assert p.proposed_text == "Won an internal hackathon with Route Pilot (Northwind Grocers, 2024)."


def test_a_year_comes_only_from_evidence_never_from_a_running_job():
    r = _resume(["Best demo award for Label Checks"])  # "3 years" is not a year; the job hasn't ended
    assert context_for(r.achievements[0], r, {}) == "Northwind Grocers"
    assert context_for("Best demo award for Label Checks", r, {"e1::Label Checks": ["Shipped in 2025."]}) \
        == "Northwind Grocers, 2025"


def test_a_company_named_already_gets_only_its_year_from_an_ended_job():
    r = _resume(["Analyst of the quarter at Fabrikam Analytics."])
    assert context_for(r.achievements[0], r, {}) == "2021"


def test_nothing_named_or_two_jobs_named_gives_no_proposal():
    r = _resume(["Speaker at a regional data conference.",
                 "Route Pilot and churn work at Fabrikam Analytics were praised.",
                 "Won the 2022 Route Pilot prize."])
    assert context_for(r.achievements[0], r, {}) is None
    assert context_for(r.achievements[1], r, {}) is None  # two jobs: not ours to guess
    assert context_for(r.achievements[2], r, {}) == "Northwind Grocers"  # has its own year
    assert [p.target_semantic_id for p in achievement_proposals(r, {})] == ["achievement::2"]


def test_only_a_parenthetical_counts_as_added_context():
    line = "Won an internal hackathon with Route Pilot."
    assert with_context("Won a prize", "Northwind Grocers") == "Won a prize (Northwind Grocers)"
    assert added_context(line, "Won an internal hackathon with Route Pilot (Northwind Grocers, 2024).") \
        == "Northwind Grocers, 2024"
    assert added_context(line, "Won a national hackathon with Route Pilot (Northwind Grocers).") is None


def _evidence(resume, notes=()):
    from app.domain.evidence import Evidence
    ev = [Evidence(id=f"ev{b.id}", source_type="experience", source_id=b.id, text=f"{e.company} — {b.group or ''}: {b.text}")
          for e in resume.experience for b in e.bullets]
    return ev + [Evidence(id=f"n{i}", source_type="project", source_id="e1::Label Checks", text=t) for i, t in enumerate(notes)]


def test_the_fact_check_passes_evidenced_context_and_rejects_anything_else():
    from app.validation.factual import FactualValidator
    r = _resume(["Won an internal hackathon with Route Pilot.", "Analyst of the quarter at Fabrikam Analytics."])
    props = achievement_proposals(r, {})
    v = FactualValidator()
    assert [v.validate_proposal(p, _evidence(r)).verdict for p in props] == ["PASS", "PASS"]  # 2021 from the job's dates
    forged = props[0].model_copy(update={"proposed_text": "Won an internal hackathon with Route Pilot (Contoso, 2019)."})
    assert v.validate_proposal(forged, _evidence(r)).verdict == "REJECT"
    reworded = props[0].model_copy(update={"proposed_text": "Won a national hackathon with Route Pilot (Northwind Grocers)."})
    assert v.validate_proposal(reworded, _evidence(r)).verdict == "REJECT"


def test_an_accepted_achievement_reaches_the_resume_and_the_match_preview(tmp_path):
    from unittest.mock import MagicMock
    from app.services.tailor import TailorService
    from tests.unit.test_project_select_p1013 import BANK, JD, REPLICA
    service = TailorService(llm_client=None)
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    bank = {**BANK, "description": BANK["description"] + "Achievements:\nWon an internal hackathon with Customer Decisioning.\n"}
    parsed, _ = service.apply_parse_corrections(service.parse_resume(REPLICA), {"added_jobs": [bank]})
    drafted = service.generate_proposals(REPLICA, JD, parsed=parsed)
    [p] = [p for p in drafted["proposals"] if p.kind == "achievement"]
    assert p.proposed_text.endswith("(Northwind Grocers).")
    result = service.tailor_resume(REPLICA, JD, str(tmp_path), preapproved_proposals=[p.model_dump()], parsed=parsed,
                                   remember_answers=False)
    import html
    page = html.unescape(open(result["html"], encoding="utf-8").read())
    assert "Customer Decisioning (Northwind Grocers)." in page
    assert result["coverage"]["lost"] == []


def test_review_p1115_counts_ordinary_words_and_a_named_company_add_nothing():
    r = _resume([])
    r.experience[0].bullets.append(ResumeBullet(id="b9", text="Built dashboards for 2000 stores.", group="Store Analytics"))
    r.experience[0].bullets.append(ResumeBullet(id="b8", text="Flew the drone.", group="Pilot"))
    assert context_for("Won a prize for Store Analytics.", r, {}) == "Northwind Grocers"  # 2000 is a count, not a year
    assert context_for("Licensed private pilot.", r, {}) is None  # a one-word heading is an ordinary word
    assert context_for("Northwind hackathon winner with Route Pilot.", r, {}) == "2024"  # the company is named in part


def test_review_p1115_achievements_start_unticked_and_strict_mode_rolls_them_back(tmp_path):
    from unittest.mock import MagicMock
    from app.services.tailor import TailorService
    from tests.unit.test_project_select_p1013 import BANK, JD, REPLICA
    r = _resume(["Won an internal hackathon with Route Pilot."])
    assert all(p.opt_in for p in achievement_proposals(r, {}))
    service = TailorService(llm_client=None)
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    bank = {**BANK, "description": BANK["description"] + "Achievements:\nWon an internal hackathon with Customer Decisioning.\n"}
    parsed, _ = service.apply_parse_corrections(service.parse_resume(REPLICA), {"added_jobs": [bank]})
    drafted = service.generate_proposals(REPLICA, JD, parsed=parsed)
    [ach] = [p.model_dump() for p in drafted["proposals"] if p.kind == "achievement"]
    bad = {**ach, "kind": "bullet", "target_semantic_id": parsed[1].resume.experience[0].bullets[0].id,
           "original_text": parsed[1].resume.experience[0].bullets[0].text, "proposed_text": "Cut costs by 97%."}
    result = service.tailor_resume(REPLICA, JD, str(tmp_path), preapproved_proposals=[ach, bad], parsed=parsed,
                                   remember_answers=False, strict_factual=True)
    import html
    page = html.unescape(open(result["html"], encoding="utf-8").read())
    assert "Customer Decisioning (Northwind Grocers)" not in page and "Customer Decisioning." in page

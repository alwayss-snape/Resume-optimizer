"""P11.1: a project bank read as a document beside the resume."""
from fastapi.testclient import TestClient

from app.analysis.project_bank import bank_lines, merge_bank, structure_to_bank
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.llm.schemas import BankStructure
from app.services.tailor import TailorService

REPLICA = "tests/fixtures/resumes/replica_layout.pdf"

# An anonymized bank in the shape owners write them: a snapshot, numbered
# projects, resume bullets, overviews, tech and figures, a to-verify note.
BANK_TEXT = """Project Bank
Career Snapshot
Harbor Foods, Bengaluru: Senior ML Engineer, March 2026 - Present
Part A - Harbor Foods (March 2026 - Present)
A1. Shopper Targeting Engine
Overview: picks each household's best next action.
Built a scoring pipeline for 6 customer actions with LightGBM propensity models.
Engineered 140 features from 2.3B transaction rows in PySpark.
Tech: PySpark, BigQuery, LightGBM
A2. Route Alert Agent (Concept)
To verify: whether this has been built beyond the design stage.
Part B - Northwind Analytics (2021 - 2024)
B1. Demand Forecasting Platform
Reduced forecast error by 18% with a gradient-boosted model.
Ran weekly demand planning reviews with category managers.
Achievements
Won an internal hackathon with Route Pilot, a procurement copilot.
Skills
Languages: Python, SQL, PySpark
"""

STRUCTURE = BankStructure(
    jobs=[{"company": "Harbor Foods", "title": "Senior ML Engineer", "start_date": "March 2026", "end_date": "Present", "line": 3},
          {"company": "Northwind Analytics", "title": "", "start_date": "2021", "end_date": "2024", "line": 11}],
    projects=[{"name": "Shopper Targeting Engine", "job": 0, "heading_line": 4, "last_line": 8},
              {"name": "Route Alert Agent (Concept)", "job": 0, "heading_line": 9, "last_line": 10},
              {"name": "Demand Forecasting Platform", "job": 1, "heading_line": 12, "last_line": 14}],
    bullet_lines=[6, 7, 13, 14], to_verify_lines=[10], achievement_lines=[16], skill_lines=[18])


def test_the_structure_keeps_the_notes_words_and_drops_bad_indices():
    lines = bank_lines(BANK_TEXT)
    data = STRUCTURE.model_dump()
    bad = BankStructure(**{**data, "projects": data["projects"] + [
        {"name": "Ghost", "job": 7, "heading_line": 1, "last_line": 2}]})  # a job that doesn't exist
    bank = structure_to_bank(lines, bad)
    harbor = bank.jobs[0]
    assert harbor.company == "Harbor Foods" and harbor.end_date == "Present"
    targeting = harbor.projects[0]
    assert targeting.name == "Shopper Targeting Engine"  # "A1." numbering dropped
    assert targeting.bullets == ["Built a scoring pipeline for 6 customer actions with LightGBM propensity models.",
                                 "Engineered 140 features from 2.3B transaction rows in PySpark."]
    assert targeting.notes == ["Overview: picks each household's best next action.", "Tech: PySpark, BigQuery, LightGBM"]
    assert [p.name for p in harbor.projects] == ["Shopper Targeting Engine"]  # the concept had only a to-verify line
    # The concept project goes whole (its heading says so), with the to-verify line.
    assert bank.to_verify == ["Route Alert Agent (Concept)", "To verify: whether this has been built beyond the design stage."]
    assert bank.achievements == ["Won an internal hackathon with Route Pilot, a procurement copilot."]
    assert all("Ghost" not in p.name for j in bank.jobs for p in j.projects)


def test_a_company_the_notes_dont_name_is_dropped():
    lines = bank_lines(BANK_TEXT)
    data = STRUCTURE.model_dump()
    made_up = BankStructure(**{**data, "jobs": [{"company": "Globex", "line": 3}, data["jobs"][1]]})
    bank = structure_to_bank(lines, made_up)
    assert [j.company for j in bank.jobs] == ["Northwind Analytics"]


def test_merging_adds_new_work_and_never_duplicates_the_resume():
    resume = Resume(candidate=Candidate(name="A B"), experience=[Experience(
        id="e1", company="Northwind Analytics Ltd", title="Data Scientist", start_date="2021", end_date="Present",
        bullets=[ResumeBullet(id="e1_b1", text="Reduced forecast error by 18% with a gradient-boosted model",
                              group="Demand Forecasting Platform")])])
    evidence = []
    bank = structure_to_bank(bank_lines(BANK_TEXT), STRUCTURE)
    notes = merge_bank(resume, evidence, bank, new_experience=lambda role: TailorService._new_experience(role, "notes"))
    northwind = next(e for e in resume.experience if e.id == "e1")
    texts = [b.text for b in northwind.bullets]
    assert texts.count("Reduced forecast error by 18% with a gradient-boosted model") == 1
    assert texts[-1] == "Ran weekly demand planning reviews with category managers."
    assert northwind.end_date == "2024"  # the notes give the end date the resume lacked
    harbor = next(e for e in resume.experience if e.company == "Harbor Foods")
    assert {b.group for b in harbor.bullets} == {"Shopper Targeting Engine"}
    project_notes = [ev.text for ev in evidence if ev.source_id == f"{harbor.id}::Shopper Targeting Engine"]
    assert "Tech: PySpark, BigQuery, LightGBM" in project_notes  # evidence, not a bullet
    assert resume.achievements == ["Won an internal hackathon with Route Pilot, a procurement copilot."]
    assert any("Added Harbor Foods" in n for n in notes) and any("Held back 2" in n for n in notes)


class _BankLLM:
    provider, model, last_error, on_wait = "fake", "fake", None, None

    def is_available(self):
        return True

    def generate_json(self, messages, schema_model, **kwargs):
        if schema_model is BankStructure:
            return STRUCTURE
        raise RuntimeError("not needed here")


def test_the_api_reads_pasted_notes_beside_the_resume(tmp_path):
    from app.api.main import create_app
    client = TestClient(create_app(make_service=lambda model=None: TailorService(llm_client=_BankLLM(), keep_run=False),
                                   serve_web=False))
    with open(REPLICA, "rb") as f:
        body = client.post("/api/parse", files={"file": ("cv.pdf", f, "application/pdf")},
                           data={"jd_text": "Senior Data Scientist. Pricing and forecasting at scale.",
                                 "bank_text": BANK_TEXT}).json()
    companies = [j["company"] for j in body["details"]["experience"]]
    assert companies[0] == "Harbor Foods"  # a current job goes first
    assert body["to_verify"] == ["Route Alert Agent (Concept)", "To verify: whether this has been built beyond the design stage."]
    assert any("Added Harbor Foods" in n for n in body["parse_notes"])


def test_without_the_ai_the_notes_are_not_read_and_the_page_says_so():
    service = TailorService(llm_client=None)
    parsed = service.parse_resume(REPLICA)
    same, notes, to_verify = service.apply_bank(parsed, bank_text=BANK_TEXT)
    assert same is parsed and to_verify == [] and "couldn't be read" in notes[0]


def test_a_project_with_notes_only_uses_them_as_its_bullets():
    lines = ["Part A - Harbor Foods (2024 - Present)", "A9. Demand Forecasting",
             "Large-scale demand forecasting covering 500K+ model IDs.", "Tech: Python, LightGBM"]
    s = BankStructure(jobs=[{"company": "Harbor Foods", "start_date": "2024", "end_date": "Present", "line": 0}],
                      projects=[{"name": "Demand Forecasting", "job": 0, "heading_line": 1, "last_line": 3}])
    project = structure_to_bank(lines, s).jobs[0].projects[0]
    assert project.bullets == ["Large-scale demand forecasting covering 500K+ model IDs."]
    assert project.notes == ["Tech: Python, LightGBM"]


class _TruncatingLLM:
    """Fails on the whole bank (its answer runs out of room), reads parts."""
    def __init__(self):
        self.calls = []

    def is_available(self):
        return True

    def generate_json(self, messages, schema_model, **kwargs):
        numbered = [int(l.split(":", 1)[0]) for l in messages[-1]["content"].splitlines()[1:]]
        self.calls.append(numbered)
        if len(numbered) > 15:
            raise RuntimeError("json_validate_failed: max completion tokens reached")
        if 13 in numbered:  # the second part: Northwind's project
            return BankStructure(jobs=[STRUCTURE.jobs[1]], projects=[STRUCTURE.projects[2].model_copy(update={"job": 0})],
                                 bullet_lines=[13, 14],
                                 achievement_lines=[16], skill_lines=[18])
        return BankStructure(jobs=[STRUCTURE.jobs[0]], projects=STRUCTURE.projects[:2], bullet_lines=[6, 7],
                             to_verify_lines=[10])


def test_a_bank_too_big_for_one_answer_is_read_in_parts(monkeypatch):
    from app.analysis import project_bank
    from app.analysis.project_bank import read_bank
    monkeypatch.setattr(project_bank, "CHUNK_LINES", 11)
    monkeypatch.setattr(project_bank, "CONTEXT_LINES", 4)
    llm = _TruncatingLLM()
    bank = read_bank(bank_lines(BANK_TEXT), llm)
    assert len(llm.calls) == 3 and llm.calls[2][:4] == [0, 1, 2, 3]  # whole, then two parts with the opening lines
    assert [j.company for j in bank.jobs] == ["Harbor Foods", "Northwind Analytics"]
    assert bank.jobs[1].projects[0].bullets[0].startswith("Reduced forecast error by 18%")
    assert bank.to_verify and bank.achievements


def test_lines_the_notes_doubt_are_held_back_whatever_the_ai_says():
    from app.analysis.project_bank import doubted_lines
    from app.llm.schemas import BankProject
    lines = ["Harbor Foods (2024 - Present)", "P1. Planner Platform",
             "Cut planning time from hours to seconds with an automated scheduler.",
             "Deployed services on Cloud Run Classic with a model registry.",
             "Note: it ran on GKE via Helm, not Cloud Run Classic. Use the revised bullets below.",
             "Built a scheduling service on GKE serving 40 depots.",
             'To verify: confirm the "hours to seconds" figure.',
             "P2. Route Agent (Concept)",
             "Agent that reroutes vans in real time."]
    held = doubted_lines(lines, set(), [BankProject(name="Route Agent", job=0, heading_line=7, last_line=8)])
    assert held == {2, 3, 4, 6, 7, 8}  # the revised line about GKE stays
    s = BankStructure(jobs=[{"company": "Harbor Foods", "line": 0}],
                      projects=[{"name": "Planner Platform", "job": 0, "heading_line": 1, "last_line": 6}],
                      bullet_lines=[2, 3, 5])  # the AI kept the doubted bullets
    bank = structure_to_bank(lines, s)
    assert bank.jobs[0].projects[0].bullets == ["Built a scheduling service on GKE serving 40 depots."]


def test_a_jobs_dates_come_from_its_own_line_when_the_ai_leaves_them_out():
    lines = ["Part B - Northwind Analytics (August 2022 – March 2026)", "B1. Forecasting", "Built forecasts for 40 stores."]
    s = BankStructure(jobs=[{"company": "Northwind Analytics", "line": 0}],
                      projects=[{"name": "Forecasting", "job": 0, "heading_line": 1, "last_line": 2}], bullet_lines=[2])
    job = structure_to_bank(lines, s).jobs[0]
    assert (job.start_date, job.end_date) == ("August 2022", "March 2026")

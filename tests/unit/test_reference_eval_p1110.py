"""P11.10: Tailores against a reference resume, judged both ways round."""
import json
import shutil
from unittest.mock import MagicMock

from app.analysis.interview import InterviewQuestion
from app.eval.reference import match_answers, run_reference
from app.services.tailor import TailorService


def test_answers_are_matched_to_this_runs_questions():
    qs = [InterviewQuestion(id="need_0", kind="need", competency="Pricing analytics", question="?"),
          InterviewQuestion(id="figure_1", kind="figure", project="Model Monitor", experience_id="e1", question="?")]
    got = match_answers(qs, {"pricing analytics": "Set the fee ratio", "Figure:model monitor": "40 pipelines",
                             "Inventory": "unused"})
    assert [(a.id, a.answer) for a in got] == [("need_0", "Set the fee ratio"), ("figure_1", "40 pipelines")]


class _Judge:
    def __init__(self, picks):
        self.picks, self.seen = list(picks), []

    def prefer(self, jd, a, b):
        self.seen.append((a[:20], b[:20]))
        return self.picks.pop(0)


def test_a_win_needs_both_orders(tmp_path):
    folder = tmp_path / "case"
    folder.mkdir()
    shutil.copy("tests/fixtures/resumes/replica_layout.pdf", folder / "resume.pdf")
    shutil.copy("tests/fixtures/resumes/replica_layout.pdf", folder / "reference.pdf")
    (folder / "jd.txt").write_text("Senior Data Scientist. Demand forecasting and pricing.", encoding="utf-8")
    (folder / "answers.json").write_text(json.dumps({"pricing": "Priced membership tiers"}), encoding="utf-8")
    service = TailorService(llm_client=None)
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    report = run_reference(str(folder), service=service, judge=_Judge(["B", "A"]))
    assert report["verdict"] == "tailores" and report["tailores_wins"] == 2
    report = run_reference(str(folder), service=service, judge=_Judge(["B", "B"]))  # position bias: no win
    assert report["verdict"] == "tie"
    assert json.loads((folder / "out" / "reference_report.json").read_text())["verdict"] == "tie"

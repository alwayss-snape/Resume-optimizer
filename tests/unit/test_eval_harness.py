"""Evaluation harness (P4.1)."""
import json

from app.eval import harness
from app.eval.__main__ import main
from app.eval.harness import Case, compare, keyword_coverage, load_cases, run


def test_committed_cases_load():
    names = [c.name for c in load_cases(include_private=False)]
    assert names == ["replica-pdf", "sample-docx", "sample-pdf"]


def test_offline_run_metrics_for_replica():
    [case] = [c for c in load_cases(include_private=False) if c.name == "replica-pdf"]
    report = run([case])
    m = report["cases"]["replica-pdf"]
    assert report["mode"] == "offline"
    assert m["parse"]["golden"] == "match" and m["parse"]["roles"] == 3 and m["parse"]["bullets"] == 7
    assert m["jd"]["requirements"] == 11 and m["jd"]["preferred"] == 3
    assert m["llm"]["calls"] == 0
    assert set(m["match"]) == {"score", "statuses", "keyword_coverage"}


def test_keyword_coverage_whole_terms():
    cov = keyword_coverage(["Python", "R", "A/B testing"], "Python and React; ran A/B testing weekly")
    assert (cov["found"], cov["total"], cov["missing"], cov["pct"]) == (2, 3, ["R"], 66.7)


def test_compare_marks_regressions():
    base = {"cases": {"x": {"match": {"score": 40.0}, "llm": {"calls": 5}}}}
    now = {"cases": {"x": {"match": {"score": 55.0}, "llm": {"calls": 9}}, "y": {}}}
    lines = compare(now, base)
    assert "  match.score: 40.0 → 55.0 (↑15.0)" in lines
    assert "  llm.calls: 5 → 9 (↑4 ⚠)" in lines
    assert "y: new case (no baseline)" in lines


def test_error_in_one_case_does_not_stop_the_run():
    report = run([Case(name="broken", resume="missing.pdf", jd="tests/fixtures/jds/sample.txt")])
    assert "error" in report["cases"]["broken"]


def test_saved_committed_report_never_contains_private_cases(tmp_path, monkeypatch):
    fake = {"generated_at": "t", "mode": "offline", "tailor": False, "cases": {
        "public": {"private": False, "error": "x"}, "secret": {"private": True, "error": "x"}}}
    monkeypatch.setattr(harness, "run", lambda *a, **k: fake)
    monkeypatch.setattr("app.eval.__main__.run", lambda *a, **k: fake)
    out = tmp_path / "baseline.json"
    main(["run", "--no-private", "--case", "replica-pdf", "--save", str(out)])
    assert list(json.loads(out.read_text())["cases"]) == ["public"]

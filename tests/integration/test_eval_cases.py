"""P4.2: every generated anonymized case must reproduce its expected.json
offline (no LLM): parse facts, JD company and keywords, page target,
education-first rule, attainable keyword coverage >= 95%, ATS round-trip,
no fabricated numbers, no keyword stuffing. Page counts are checked when
LibreOffice is installed."""
import json
import subprocess
import sys

import pytest

from app.eval.harness import GENERATED_MANIFEST, fabricated_numbers, load_cases, run, stuffing

GENERATED = [c for c in load_cases(include_private=False) if c.suite == "generated"]


def test_generated_cases_exist():
    with open(GENERATED_MANIFEST, encoding="utf-8") as f:
        assert len(json.load(f)) == len(GENERATED) == 8


@pytest.mark.eval
@pytest.mark.parametrize("case", GENERATED, ids=[c.name for c in GENERATED])
def test_case_meets_expected(case, tmp_path):
    metrics = run([case], tailor=True, out_dir=str(tmp_path))["cases"][case.name]
    assert "error" not in metrics, metrics.get("error")
    assert metrics["expected"]["failed"] == []


def test_fabricated_numbers_and_stuffing_detectors():
    assert fabricated_numbers("Cut costs by 35% for 2,000 users in 2024.", "cut costs 35% for 2000 users 2024") == []
    assert fabricated_numbers("Served 5M users.", "Served users.") == ["5M"]
    assert fabricated_numbers("Cut costs 12% across teams.", "Led 12 teams.") == ["12%"]  # units matter
    assert fabricated_numbers("2021 - 2025\nB.S. in CS", "2021 - 2025 B.S. in CS") == []
    assert stuffing("Python " * 6, ["Python"], 60.0, 50.0)["repeated"] == {"Python": 6}
    assert stuffing("SAP " * 7, ["SAP"], 60.0, 50.0, source_text="SAP " * 7)["ok"]  # the resume had them (P9.16)
    assert stuffing("SAP " * 8, ["SAP"], 60.0, 50.0, source_text="SAP " * 7)["repeated"] == {"SAP": 8}
    assert stuffing("", [], 90.0, 95.0)["ok"]  # already above the band before tailoring: not stuffing
    assert not stuffing("", [], 90.0, 70.0)["ok"]


def test_check_flag_passes_for_a_clean_case(tmp_path):
    """Offline parse / JD / keyword checks (no rendering) in the default suite."""
    out = subprocess.run([sys.executable, "-m", "app.eval", "run", "--no-private", "--case", "new-grad", "--check"],
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout[-1500:]

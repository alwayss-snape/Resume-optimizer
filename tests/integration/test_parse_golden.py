"""Parse a resume and compare it, field by field, with a hand-checked golden
file (Stage A exit gate).

The replica case is committed. The real-resume case runs only on a machine
that has the private files in data/eval/private/ (gitignored), so it's
skipped in CI and on fresh clones.

To create or refresh a golden file after checking the parse by eye:
    python tests/integration/test_parse_golden.py <resume.pdf|docx> > <golden.json>
"""
import json
import os
import sys

import pytest

from app.eval.golden import project

CASES = [
    ("tests/fixtures/resumes/replica_layout.pdf", "tests/fixtures/resumes/replica_layout.golden.json"),
    ("data/eval/private/resume.pdf", "data/eval/private/resume.golden.json"),
]


@pytest.mark.parametrize("resume_path,golden_path", CASES, ids=["replica", "private-real-resume"])
def test_parse_matches_golden(resume_path, golden_path):
    if not (os.path.exists(resume_path) and os.path.exists(golden_path)):
        pytest.skip(f"{resume_path} / {golden_path} not present")
    with open(golden_path, encoding="utf-8") as f:
        golden = json.load(f)
    parsed = project(resume_path)
    for key in golden:
        assert parsed[key] == golden[key], f"{key} differs from {golden_path}"


if __name__ == "__main__":
    print(json.dumps(project(sys.argv[1]), indent=2, ensure_ascii=False))

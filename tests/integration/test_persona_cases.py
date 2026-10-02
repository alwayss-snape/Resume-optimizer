"""P8.1: the cross-domain user-testing personas as eval cases (offline, no LLM).

Two checks per persona:
- content: what was read and kept (contact, each job's title / company /
  dates / bullets, education, phrases that must reach the output file);
- full: every expected.json check, including the generic ones (attainable
  keyword coverage, page target, ATS round-trip, fabricated numbers,
  stuffing).

Known failures are listed below as strict xfails, so a fix that makes a case
pass fails the test until the case is taken off the list. Each Phase 8 item
shrinks these lists; Stage H's exit gate is an empty CONTENT_XFAIL.
"""
import json

import pytest

from app.eval.harness import PERSONA_MANIFEST, is_content_failure, load_cases, run

PERSONAS = [c for c in load_cases(include_private=False, include_personas=True) if c.suite == "persona"]

# Persona -> why it still fails. Remove an entry when the case passes.
CONTENT_XFAIL = {
    'teacher': 'two degrees merged (P8.8)',
    'lawyer': 'two degrees merged (P8.8)',
    'academic': 'two degrees merged (P8.8)',
    'executive': 'two degrees merged (P8.8)',
}
# Until Stage K, scoring and page checks fail for most personas too.
FULL_XFAIL = {name: 'content (see CONTENT_XFAIL), scoring (Stage K) or page target (P8.16)'
              for name in [*CONTENT_XFAIL, 'newgrad', 'eu_cv', 'spanish', 'nurse', 'sales', 'lawyer', 'academic',
                           'executive', 'gap', 'veteran', 'eu_en', 'india', 'federal', 'nurse-pdf', 'sales-pdf']}

_RESULTS = {}


def _failures(case, tmp_path_factory):
    if case.name not in _RESULTS:
        out = tmp_path_factory.mktemp(case.name.replace("_", "-"))
        metrics = run([case], tailor=True, out_dir=str(out))["cases"][case.name]
        assert "error" not in metrics, metrics.get("error")
        _RESULTS[case.name] = metrics["expected"]["failed"]
    return _RESULTS[case.name]


def _params(xfail):
    return [pytest.param(c, id=c.name, marks=pytest.mark.xfail(reason=xfail[c.name], strict=True)
                         if c.name in xfail else ()) for c in PERSONAS]


def test_persona_cases_exist():
    with open(PERSONA_MANIFEST, encoding="utf-8") as f:
        assert len(json.load(f)) == len(PERSONAS) >= 20


@pytest.mark.eval
@pytest.mark.parametrize("case", _params(CONTENT_XFAIL))
def test_persona_content(case, tmp_path_factory):
    assert [m for m in _failures(case, tmp_path_factory) if is_content_failure(m)] == []


@pytest.mark.eval
@pytest.mark.parametrize("case", _params(FULL_XFAIL))
def test_persona_full(case, tmp_path_factory):
    assert _failures(case, tmp_path_factory) == []

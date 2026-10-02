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

PERSONAS = [c for c in load_cases(include_private=False) if c.suite == "persona"]

# Persona -> why it still fails. Remove an entry when the case passes.
CONTENT_XFAIL = {
    'nurse': 'phone (P8.4); title<tab>company lines and MM/YYYY dates (P8.5, P8.6); rotations, languages, volunteer (P8.3)',
    'nurse-pdf': 'phone (P8.4); MM/YYYY dates (P8.6); unknown sections (P8.3)',
    'teacher': "'Professional Journey' and training sections dropped (P8.3); two degrees merged (P8.8); portfolio link (P8.4)",
    'electrician': "'Title, Company, dates' lines (P8.5); licences and training sections (P8.3)",
    'warehouse': "'Delivery Driver' not a role word (P8.5)",
    'retail': "phone (P8.4); 'Title, Company, City' lines (P8.5)",
    'sales': "'Title, Company, City<tab>dates' lines (P8.5)",
    'sales-pdf': 'PDF job lines and bullets (P8.5, P8.7)',
    'accountant': "'Title, Company, City<tab>MM/YYYY' lines (P8.5, P8.6); certification split on commas (P8.3)",
    'lawyer': '100+ character job line read as a bullet (P8.5); bar admissions, publications, references (P8.3)',
    'academic': 'appointments read as education, publications and grants (P8.3)',
    'designer': "name from the page header and portfolio link (P8.4, P8.7); 'Title, Company' lines (P8.5)",
    'executive': 'role words (P8.5); two degrees merged (P8.8); board section (P8.3)',
    'newgrad': 'phone (P8.4); activities split on commas (P8.3)',
    'gap': 'role words (P8.5)',
    'veteran': "'Title, Company, City<tab>dates' lines (P8.5)",
    'eu_cv': 'German headings drop everything (P8.3); phone (P8.4); personal details (P8.3)',
    'eu_en': 'phone (P8.4); DD/MM/YYYY dates (P8.6); job lines (P8.5); languages and hobbies (P8.3)',
    'spanish': 'Spanish headings drop everything (P8.3); phone (P8.4)',
    'india': "phone (P8.4); 'Till Date' (P8.6); job lines (P8.5); personal details and declaration (P8.3)",
    'federal': 'job header over three lines (P8.5); address in the header (P8.3)',
    'textbox': 'text boxes ignored (P8.7)',
}
# Until Stage K, scoring and page checks fail for most personas too.
FULL_XFAIL = {name: 'content (see CONTENT_XFAIL), scoring (Stage K) or page target (P8.16)' for name in CONTENT_XFAIL}

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

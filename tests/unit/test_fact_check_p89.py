"""P8.9: the fact check catches wording borrowed from the job description,
facts taken from another job, and new claims, with one rule for verbs."""
from app.analysis.rewriter import RewriteProposal
from app.domain.evidence import Evidence
from app.validation.factual import FactualValidator

NURSE_EVIDENCE = [
    Evidence(id="e1", source_type="experience", source_id="exp_002_b01",
             text="St. Joseph's Hospital: Cared for 5-6 post-operative patients per shift, including wound care"),
    Evidence(id="e2", source_type="experience", source_id="exp_001_b01",
             text="Banner University Medical Center: Provide direct patient care for 4-5 telemetry patients"),
    Evidence(id="e3", source_type="other", source_id="sec_01",
             text="Clinical Rotations: ICU - Mayo Clinic Hospital (120 hrs), Spring 2019"),
    Evidence(id="e4", source_type="skill", source_id="skill_1", text="Epic"),
]
JD = ("We are seeking a compassionate ICU nurse. Monitor hemodynamics, titrate vasoactive drips, manage "
      "ventilated patients. Document care accurately in Epic. Collaborate with interdisciplinary team.")


def _check(original, rewritten, sem_id="exp_002_b01", evidence=NURSE_EVIDENCE, jd=JD):
    prop = RewriteProposal(target_semantic_id=sem_id, original_text=original, proposed_text=rewritten,
                           evidence_ids=[e.id for e in evidence])
    return FactualValidator().validate_proposal(prop, evidence, jd_keywords=["ICU", "Epic"], jd_text=jd)


ORIG = "Cared for 5-6 post-operative patients per shift, including wound care"


def test_fact_from_another_section_is_rejected():
    res = _check(ORIG, "Administered direct ICU patient care for 5-6 post-operative patients per shift at "
                       "Mayo Clinic Hospital, including wound care")
    assert res.verdict == "REJECT"
    assert any("another part of your resume" in w for w in res.warnings)


def test_skill_from_the_skills_list_needs_confirmation_not_rejection():
    res = _check(ORIG, "Cared for 5-6 post-operative patients per shift in Epic, including wound care")
    assert res.verdict == "NEEDS_CONFIRM"


def test_jd_only_wording_is_rejected():
    res = _check(ORIG, "Cared for 5-6 ventilated post-operative patients per shift, including wound care")
    assert res.verdict == "REJECT"
    assert any("job description" in w and "ventilated" in w for w in res.warnings)
    res = _check(ORIG, "Compassionately cared for 5-6 post-operative patients per shift, including wound care")
    assert res.verdict == "REJECT"  # another form of the JD's "compassionate" is still its wording
    res = _check(ORIG, "Cared accurately for 5-6 post-operative patients per shift, including wound care")
    assert res.verdict == "REJECT"


def test_new_claim_words_need_confirmation():
    evidence = [Evidence(id="e1", source_type="experience", source_id="exp_001_b01",
                         text="Lakeshore Electric: Read blueprints and follow NEC code")]
    res = _check("Read blueprints and follow NEC code", "Enhanced safety standards through NEC code compliance "
                 "while reading blueprints", sem_id="exp_001_b01", evidence=evidence, jd="Electrician. NFPA 70E.")
    assert res.verdict == "NEEDS_CONFIRM"
    assert any("safety" in w and "standards" in w for w in res.warnings)


def test_plain_rewording_still_passes():
    res = _check(ORIG, "Cared for 5-6 post-operative patients each shift, including wound care")
    assert res.verdict == "PASS", res.warnings


def test_scope_verbs_follow_one_rule():
    evidence = [Evidence(id="e1", source_type="experience", source_id="exp_001_b01",
                         text="Acme: Precept new graduate nurses; trained 8 orientees on Epic charting")]
    original = "Precept new graduate nurses; trained 8 orientees on Epic charting"
    ok = _check(original, "Trained 8 orientees on Epic charting and precept new graduate nurses",
                sem_id="exp_001_b01", evidence=evidence, jd="")
    assert ok.verdict == "PASS", ok.warnings
    claim = _check(original, "Supervised 8 orientees on Epic charting and precept new graduate nurses",
                   sem_id="exp_001_b01", evidence=evidence, jd="")
    assert claim.verdict == "REJECT"  # a supervision claim the resume never makes

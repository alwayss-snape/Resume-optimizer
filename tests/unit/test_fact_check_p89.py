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


def test_jd_only_wording_is_flagged_and_two_words_are_rejected():
    """One JD-only word needs a look (Stage I review); two or more are the JD's claim."""
    res = _check(ORIG, "Cared for 5-6 ventilated post-operative patients per shift, including wound care")
    assert res.verdict == "NEEDS_CONFIRM" and any("ventilated" in w for w in res.warnings)
    res = _check(ORIG, "Compassionately cared for 5-6 post-operative patients per shift, including wound care")
    assert res.verdict == "NEEDS_CONFIRM"  # another form of the JD's "compassionate"
    res = _check(ORIG, "Cared accurately for 5-6 ventilated post-operative patients per shift, including wound care")
    assert res.verdict == "REJECT" and any("job description" in w for w in res.warnings)


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


def test_dropping_a_superlative_needs_confirmation():
    """P8.11: "largest deal in company history" -> "largest company deal" weakens a claim."""
    evidence = [Evidence(id="e1", source_type="experience", source_id="exp_001_b01",
                         text="CloudMetrics: Closed largest deal in company history ($480K ACV) with a retailer")]
    res = _check("Closed largest deal in company history ($480K ACV) with a retailer",
                 "Closed a $480K ACV deal with a retailer", sem_id="exp_001_b01", evidence=evidence, jd="")
    assert res.verdict == "NEEDS_CONFIRM" and any("largest" in w for w in res.warnings)


def test_irregular_past_tense_and_generic_words_are_not_claims():
    """Stage I gate: "Troubleshoot" -> "Troubleshot" drops nothing; "experience" claims nothing."""
    evidence = [Evidence(id="e1", source_type="experience", source_id="exp_001_b01",
                         text="Lakeshore Electric: Troubleshoot motors and controls")]
    res = _check("Troubleshoot motors and controls", "Troubleshot motors and controls",
                 sem_id="exp_001_b01", evidence=evidence, jd="Troubleshooting PLCs. 5+ years experience.")
    assert res.verdict == "PASS", res.warnings


TWO_JOBS = [
    Evidence(id="e1", source_type="experience", source_id="exp_002_b01",
             text="St. Joseph's Hospital: Cared for 5-6 post-operative patients per shift, including wound care"),
    Evidence(id="e2", source_type="experience", source_id="exp_001_b01",
             text="Banner: Titrate cardiac drips (diltiazem, heparin) per protocol and monitor rhythms"),
    Evidence(id="e3", source_type="certification", source_id="c1", text="ACLS - American Heart Association"),
]


def test_plain_words_from_another_job_are_rejected():
    """Stage I review: "titrating cardiac drips" belongs to the other hospital."""
    res = _check(ORIG, "Cared for 5-6 post-operative patients per shift, titrating cardiac drips and monitoring "
                       "rhythms, including wound care", evidence=TWO_JOBS, jd="")
    assert res.verdict == "REJECT" and any("another job" in w for w in res.warnings)


def test_a_credential_belongs_to_the_person_not_one_job():
    res = _check(ORIG, "Cared for 5-6 post-operative patients per shift per ACLS protocol, including wound care",
                 evidence=TWO_JOBS, jd="")
    assert res.verdict == "NEEDS_CONFIRM", res.warnings


def test_one_borrowed_word_is_a_check_not_a_rejection_and_spellings_match():
    res = _check(ORIG, "Cared for 5-6 critically-ill post-operative patients per shift, including wound care",
                 jd="Provide direct patient care to critically ill patients.")
    assert res.verdict == "NEEDS_CONFIRM"  # hyphenated parts are checked too
    evidence = [Evidence(id="e1", source_type="experience", source_id="exp_001_b01",
                         text="Acme: Containerised the service with Docker")]
    res = _check("Containerised the service with Docker", "Containerized the service with Docker",
                 sem_id="exp_001_b01", evidence=evidence, jd="Containerized services with Docker")
    assert res.verdict == "PASS", res.warnings
    evidence = [Evidence(id="e1", source_type="experience", source_id="exp_001_b01",
                         text="Lakeshore: Install and repair wiring, conduit, panels")]
    res = _check("Install and repair wiring, conduit, panels", "Installed and repaired electrical wiring, conduit and "
                 "panels", sem_id="exp_001_b01", evidence=evidence, jd="Industrial electrical experience.")
    assert res.verdict == "NEEDS_CONFIRM", res.warnings

"""P3.2: confirmed gap answers are saved locally and offered on the next JD."""
import json
import os
import shutil
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

from app.analysis.gap_questions import GapQuestion
from app.config.settings import settings
from app.services.profile_store import ProfileStore


def _q(qid="gap_1", keywords=("Kafka", "Flink"), requirement="Streaming with Kafka or Flink"):
    return GapQuestion(id=qid, requirement=requirement, priority="required", keywords=list(keywords), question="?")


def test_record_and_known_are_case_insensitive(tmp_path):
    store = ProfileStore(str(tmp_path / "p" / "facts.json"))
    saved = store.record([{"question_id": "gap_1", "confirmed_keywords": ["Kafka"],
                           "answer": "Ran a Kafka cluster at Acme."}], [_q()])
    assert saved == ["Kafka"]
    known = store.known(["kafka", "Flink"])
    assert list(known) == ["kafka"]
    assert known["kafka"].answer == "Ran a Kafka cluster at Acme."
    assert known["kafka"].requirement == "Streaming with Kafka or Flink"


def test_new_answer_replaces_blank_keeps(tmp_path):
    store = ProfileStore(str(tmp_path / "facts.json"))
    store.record([{"question_id": "gap_1", "confirmed_keywords": ["Kafka"], "answer": "First."}], [_q()])
    store.record([{"question_id": "x", "confirmed_keywords": ["Kafka"], "answer": ""}], [])
    assert store.known(["Kafka"])["Kafka"].answer == "First."
    store.record([{"question_id": "x", "confirmed_keywords": ["Kafka"], "answer": "Second."}], [])
    assert store.known(["Kafka"])["Kafka"].answer == "Second."


def test_nothing_ticked_writes_nothing(tmp_path):
    path = tmp_path / "facts.json"
    assert ProfileStore(str(path)).record([{"question_id": "gap_1", "confirmed_keywords": [], "answer": "x"}],
                                          [_q()]) == []
    assert not path.exists()


def test_forget_one_and_all(tmp_path):
    store = ProfileStore(str(tmp_path / "facts.json"))
    store.record([{"question_id": "gap_1", "confirmed_keywords": ["Kafka", "Flink"], "answer": ""}], [_q()])
    assert store.forget("KAFKA") == 1 and list(store.known(["Kafka", "Flink"])) == ["Flink"]
    assert store.forget() == 1 and store.known(["Flink"]) == {}


def test_corrupt_file_starts_fresh_and_is_kept(tmp_path):
    path = tmp_path / "facts.json"
    path.write_text("{not json")
    store = ProfileStore(str(path))
    assert store.load().facts == {}
    assert (tmp_path / "facts.json.corrupt").exists()


def test_tests_never_touch_the_real_profile():
    assert "profile_test_" in settings.profile_path
    assert os.path.abspath(settings.profile_path) != os.path.abspath("data/profile/facts.json")


# -- wired into the service and UI --------------------------------------------

def _service(tmp_path):
    from app.eval.harness import OfflineLLM
    from app.services.run_manager import RunManager
    from app.services.tailor import TailorService
    service = TailorService(llm_client=OfflineLLM())
    service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    service.profile_store = ProfileStore(str(tmp_path / "facts.json"))
    return service


JD = "Requirements:\n- Experience with Kafka or Flink for streaming.\n- Python."


def test_saved_answers_prefill_the_next_jds_questions(tmp_path):
    service = _service(tmp_path)
    service.profile_store.record([{"question_id": "q", "confirmed_keywords": ["Kafka"],
                                   "answer": "Ran Kafka consumers at Acme."}], [])
    questions = service.generate_proposals("tests/fixtures/resumes/sample.docx", JD)["gap_questions"]
    q = next(q for q in questions if "Kafka" in q.keywords)
    assert q.saved_keywords == ["Kafka"] and q.saved_answer == "Ran Kafka consumers at Acme."


def test_tailor_saves_ticked_answers_unless_told_not_to(tmp_path):
    answers = [{"question_id": "gap_1", "confirmed_keywords": ["Kafka"], "answer": "", "target": "auto"}]
    service = _service(tmp_path)
    service.tailor_resume("tests/fixtures/resumes/sample.docx", JD, str(tmp_path / "a"), gap_answers=answers,
                          remember_answers=False)
    assert service.profile_store.known(["Kafka"]) == {}
    service.tailor_resume("tests/fixtures/resumes/sample.docx", JD, str(tmp_path / "b"), gap_answers=answers)
    assert "Kafka" in service.profile_store.known(["Kafka"])


def test_ui_prefills_and_forgets(tmp_path):
    from app.services.tailor import TailorService
    ProfileStore().record([{"question_id": "q", "confirmed_keywords": ["PyTorch"], "answer": "Trained CNNs."}], [])
    question = GapQuestion(id="gap_1", requirement="PyTorch", priority="required", keywords=["PyTorch", "JAX"],
                           question="?", saved_keywords=["PyTorch"], saved_answer="Trained CNNs.")
    resume_copy = tmp_path / "upload.docx"
    shutil.copy("tests/fixtures/resumes/sample.docx", resume_copy)
    at = AppTest.from_file(os.path.abspath("app/ui.py"), default_timeout=60)
    for key, value in {"stage": "proposals", "proposals": [], "gap_questions": [question], "experience_options": [],
                       "resume_path": str(resume_copy), "jd_text": "x", "model_choice": "m",
                       "render_mode": "ATS_DEFAULT", "strict_factual": False, "pre_score": 10.0}.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception
    boxes = {c.label: c.value for c in at.checkbox if c.label.startswith("I have used")}
    assert boxes == {"I have used PyTorch": True, "I have used JAX": False}
    assert at.text_area(key="gap_1_answer").value == "Trained CNNs."
    with patch.object(TailorService, "tailor_resume", return_value={"success": True}) as tailor:
        next(b for b in at.button if b.label == "Apply & Generate").click().run()
    kwargs = tailor.call_args.kwargs
    assert kwargs["remember_answers"] is True and kwargs["gap_questions"][0].id == "gap_1"
    at.session_state["stage"] = "idle"
    at.run()
    next(b for b in at.sidebar.button if b.label.startswith("Forget")).click().run()
    assert ProfileStore().load().facts == {}


# -- review fixes ----------------------------------------------------------------

def test_prefilled_answer_is_not_copied_to_other_ticked_keywords(tmp_path):
    store = ProfileStore(str(tmp_path / "facts.json"))
    store.record([{"question_id": "q", "confirmed_keywords": ["Kafka"], "answer": "Ran Kafka at Acme."}], [])
    # Next JD: question [Kafka, Flink] pre-filled with Kafka's answer; user ticks both, leaves text.
    store.record([{"question_id": "q2", "confirmed_keywords": ["Kafka", "Flink"], "answer": "Ran Kafka at Acme."}],
                 [])
    known = store.known(["Kafka", "Flink"])
    assert known["Kafka"].answer == "Ran Kafka at Acme." and known["Flink"].answer == ""


def test_unreadable_profile_is_left_alone(tmp_path):
    folder = tmp_path / "is_a_dir"
    folder.mkdir()
    assert ProfileStore(str(folder)).load().facts == {}
    assert folder.is_dir() and not (tmp_path / "is_a_dir.corrupt").exists()


def test_forget_on_empty_profile_writes_nothing(tmp_path):
    path = tmp_path / "facts.json"
    assert ProfileStore(str(path)).forget() == 0 and not path.exists()


def test_unticked_question_withdraws_the_prefilled_answer(tmp_path):
    from app.services.tailor import TailorService
    question = GapQuestion(id="gap_1", requirement="PyTorch", priority="required", keywords=["PyTorch"],
                           question="?", saved_keywords=["PyTorch"], saved_answer="Trained CNNs.")
    resume_copy = tmp_path / "upload.docx"
    shutil.copy("tests/fixtures/resumes/sample.docx", resume_copy)
    at = AppTest.from_file(os.path.abspath("app/ui.py"), default_timeout=60)
    for key, value in {"stage": "proposals", "proposals": [], "gap_questions": [question], "experience_options": [],
                       "resume_path": str(resume_copy), "jd_text": "x", "model_choice": "m",
                       "render_mode": "ATS_DEFAULT", "strict_factual": False, "pre_score": 10.0}.items():
        at.session_state[key] = value
    at.run()
    next(c for c in at.checkbox if c.label == "I have used PyTorch").uncheck()
    with patch.object(TailorService, "tailor_resume", return_value={"success": True}) as tailor:
        next(b for b in at.button if b.label == "Apply & Generate").click().run()
    assert tailor.call_args.kwargs["gap_answers"] == []


def test_start_over_clears_gap_widgets(tmp_path):
    at = AppTest.from_file(os.path.abspath("app/ui.py"), default_timeout=60)
    at.session_state["stage"] = "proposals"
    at.session_state["gap_1_Kafka"] = True
    at.session_state["gap_1_answer"] = "old answer"
    at.run()
    next(b for b in at.sidebar.button if b.label == "🔄 Start Over").click().run()
    assert "gap_1_Kafka" not in at.session_state and "gap_1_answer" not in at.session_state

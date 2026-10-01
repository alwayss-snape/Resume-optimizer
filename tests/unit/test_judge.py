"""P4.3: LLM-as-judge (rubric + position-swapped pairwise), with a fake
judge model: no live calls."""
import shutil
from unittest.mock import MagicMock

from app.eval.harness import Case, replay_case, run
from app.eval.judge import ResumeJudge, report_markdown
from app.llm.schemas import JudgePairwise, JudgeRubric

RUBRIC = JudgeRubric(relevance=4, clarity=4, faithfulness=5, ats_readability=5, overall=4,
                     unsupported_claims=[], strengths=["Leads with JD skills"], weaknesses=["Few metrics"])


def _client(pairwise_answers):
    client = MagicMock(provider="groq", model="qwen/qwen3.8-27b")
    answers = iter(pairwise_answers)

    def generate_json(messages, schema_model, **kw):
        if schema_model is JudgeRubric:
            return RUBRIC
        winner = next(answers)
        if callable(winner):  # decide from the prompt, e.g. by which slot holds the tailored text
            winner = winner(messages[1]["content"])
        return JudgePairwise(winner=winner, reason="r")
    client.generate_json.side_effect = generate_json
    return client


def test_tailored_wins_only_when_it_wins_both_orders():
    prefers_tailored = lambda prompt: "A" if prompt.index("TAILORED-TEXT") < prompt.index("ORIGINAL-TEXT") else "B"
    out = ResumeJudge(_client([prefers_tailored, prefers_tailored])).judge("JD", "ORIGINAL-TEXT", "TAILORED-TEXT")
    assert out["rubric"]["overall"] == 4 and out["strengths"] == ["Leads with JD skills"]
    assert out["pairwise"] == {"tailored_wins": 2, "original_wins": 0, "verdict": "tailored"}


def test_position_bias_cancels_out():
    out = ResumeJudge(_client(["A", "A"])).judge("JD", "orig", "tail")  # always picks the first slot
    assert out["pairwise"]["verdict"] == "inconsistent/tie"
    assert out["pairwise"]["tailored_wins"] == 1 and out["pairwise"]["original_wins"] == 1


def test_a_failed_judge_call_is_reported_not_raised():
    client = MagicMock(provider="groq", model="m")
    client.generate_json.side_effect = RuntimeError("429 daily limit")
    out = ResumeJudge(client).judge("JD", "o", "t")
    assert "429" in out["rubric_error"] and "429" in out["pairwise_error"]


def test_replay_judges_saved_output_without_generating(tmp_path, monkeypatch):
    import app.eval.harness as harness
    case_dir = tmp_path / "sample-docx"
    case_dir.mkdir()
    shutil.copy("tests/fixtures/resumes/sample.docx", case_dir / "Jane_Doe_Resume_X.docx")
    seen = {}

    def fake_judge(jd, original, tailored):
        seen.update(jd=jd, original=original, tailored=tailored)
        return {"judge_model": "fake", "rubric": {k: 3 for k in ("relevance", "clarity", "faithfulness",
                                                                    "ats_readability", "overall")},
                "pairwise": {"tailored_wins": 1, "original_wins": 1, "verdict": "inconsistent/tie"}}
    monkeypatch.setattr(harness, "_judge", fake_judge)
    case = Case(name="sample-docx", resume="tests/fixtures/resumes/sample.docx", jd="tests/fixtures/jds/sample.txt")
    report = run([case], replay=str(tmp_path))
    m = report["cases"]["sample-docx"]
    assert m["judge"]["rubric"]["overall"] == 3 and seen["tailored"] and seen["original"] and seen["jd"]
    md = report_markdown(report)
    assert "## sample-docx" in md and "inconsistent/tie" in md
    assert "error" in replay_case(Case(name="missing", resume=case.resume, jd=case.jd), str(tmp_path))


def test_judge_flag_requires_live_tailor(capsys):
    from app.eval.__main__ import main
    assert main(["run", "--no-private", "--case", "sample-docx", "--judge"]) == 1
    assert "needs --live --tailor" in capsys.readouterr().out


def test_think_blocks_are_stripped_from_json():
    from unittest.mock import patch
    from app.llm.client import LLMClient
    with patch("ollama.Client") as mock_ollama:
        inst = MagicMock()
        inst.chat.return_value = {"message": {"content": '<think>hmm</think>{"winner": "A", "reason": "x"}'}}
        mock_ollama.return_value = inst
        result = LLMClient(provider="ollama", model="m").generate_json([{"role": "user", "content": "q"}],
                                                                       JudgePairwise)
    assert result.winner == "A"

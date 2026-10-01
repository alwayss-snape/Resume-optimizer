"""LLM-as-judge for the evaluation harness (P4.3).

A model from a different family than the generator (settings.judge_model,
Qwen on Groq by default; the generator is gpt-oss) reviews each tailored
resume:

- rubric: 1-5 for relevance, clarity, faithfulness to the original, ATS
  readability and overall, plus any claims the original doesn't support;
- pairwise: original vs tailored, asked twice with the positions swapped.
  The tailored version only counts as better when it wins both ways, so a
  judge's preference for whichever comes first (or second) cancels out.

Three judge calls per case. Used by `python -m app.eval run --live --tailor
--judge` and, without regenerating anything, `--replay DIR`.
"""
import os
import re
from typing import Dict, Optional

from app.config.settings import settings
from app.llm.schemas import JudgePairwise, JudgeRubric

_PROMPTS = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts")
RUBRIC_KEYS = ("relevance", "clarity", "faithfulness", "ats_readability", "overall")


def _prompt(name: str) -> str:
    with open(os.path.join(_PROMPTS, name), encoding="utf-8") as f:
        return f.read()


def judge_client(provider: Optional[str] = None, model: Optional[str] = None):
    from app.llm.client import LLMClient
    return LLMClient(provider=provider or settings.judge_provider, model=model or settings.judge_model)


class ResumeJudge:
    def __init__(self, client=None):
        self.client = client or judge_client()

    def _ask(self, system: str, user: str, schema):
        return self.client.generate_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            schema_model=schema, temperature=0.0)

    def rubric(self, jd: str, original: str, tailored: str) -> JudgeRubric:
        return self._ask(_prompt("final_review.txt"),
                         f"JOB DESCRIPTION:\n{jd}\n\nORIGINAL RESUME:\n{original}\n\nTAILORED RESUME:\n{tailored}",
                         JudgeRubric)

    def prefer(self, jd: str, a: str, b: str) -> str:
        result = self._ask(_prompt("judge_pairwise.txt"),
                           f"JOB DESCRIPTION:\n{jd}\n\nRESUME A:\n{a}\n\nRESUME B:\n{b}", JudgePairwise)
        # "A", "a", "A.", "Resume A", "Version B" -> A / B; anything else is a tie.
        m = re.fullmatch(r"\s*(?:resume|version)?\s*([AB])\W*", result.winner or "", re.IGNORECASE)
        return m.group(1).upper() if m else "TIE"

    def judge(self, jd: str, original: str, tailored: str) -> Dict:
        """Rubric + position-swapped pairwise for one case. A failed call is
        reported in the result instead of raising, so one case can't sink a run."""
        out: Dict = {"judge_model": f"{self.client.provider}/{self.client.model}"}
        try:
            r = self.rubric(jd, original, tailored)
            out["rubric"] = {k: getattr(r, k) for k in RUBRIC_KEYS}
            out["unsupported_claims"] = r.unsupported_claims
            out["strengths"], out["weaknesses"] = r.strengths, r.weaknesses
        except Exception as e:
            out["rubric_error"] = str(e)[:300]
        try:
            first = self.prefer(jd, original, tailored)   # tailored is B
            second = self.prefer(jd, tailored, original)  # tailored is A
            wins = (first == "B") + (second == "A")
            losses = (first == "A") + (second == "B")
            out["pairwise"] = {
                "tailored_wins": wins, "original_wins": losses,
                "verdict": "tailored" if wins == 2 else "original" if losses == 2 else "inconsistent/tie",
            }
        except Exception as e:
            out["pairwise_error"] = str(e)[:300]
        return out


def _one_line(text) -> str:
    return " ".join(str(text).split())


def report_markdown(report: Dict) -> str:
    """A dated, human-readable judge report for a run."""
    lines = [f"# Judge report: {report['generated_at']}", "", f"Mode: {report['mode']}", ""]
    for name, m in report["cases"].items():
        j = (m.get("tailor") or {}).get("judge") or m.get("judge")
        if not j:
            continue
        lines += [f"## {name}", "", f"Judge: `{j.get('judge_model')}`", ""]
        if "rubric" in j:
            lines += ["| " + " | ".join(RUBRIC_KEYS) + " |", "|" + "---|" * len(RUBRIC_KEYS),
                      "| " + " | ".join(str(j["rubric"][k]) for k in RUBRIC_KEYS) + " |", ""]
            for title, key in (("Unsupported claims", "unsupported_claims"), ("Strengths", "strengths"),
                               ("Weaknesses", "weaknesses")):
                if j.get(key):
                    lines += [f"**{title}:**"] + [f"- {_one_line(x)}" for x in j[key]] + [""]
        if "pairwise" in j:
            p = j["pairwise"]
            lines += [f"**Pairwise (positions swapped):** {p['verdict']} "
                      f"(tailored won {p['tailored_wins']} of 2, original {p['original_wins']} of 2)", ""]
        for key in ("rubric_error", "pairwise_error"):
            if j.get(key):
                lines += [f"**{key}:** {_one_line(j[key])}", ""]
    return "\n".join(lines)

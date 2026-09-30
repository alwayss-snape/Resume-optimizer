import os
import re
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import Field

from app.analysis.change_proposal import ChangeProposal
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.resume import Experience, Resume
from app.domain.tailoring import TailoringAction, TailoringPlan
from app.llm.client import LLMClient
from app.llm.schemas import BulletRewriteResult, RoleRewriteResult


# Typographic Unicode that some models (e.g. gpt-oss) emit: non-breaking /
# narrow / thin spaces and non-breaking hyphens. They look identical but
# break keyword matching, number checks and ATS parsing, so LLM output is
# normalised to plain ASCII spaces and hyphens.
_UNICODE_SPACES = re.compile(r"[\u00a0\u2007\u2009\u200a\u202f\u205f]")
_UNICODE_HYPHENS = re.compile(r"[\u2010\u2011\u2012]")
# A number split from its unit by a space ("50 M" -> "50M").
_SPLIT_UNIT = re.compile(r"(\d)\s+([KMBkmb])(?![A-Za-z])")


def normalize_llm_text(text: str) -> str:
    text = _UNICODE_SPACES.sub(" ", text or "")
    text = _UNICODE_HYPHENS.sub("-", text)
    text = _SPLIT_UNIT.sub(r"\1\2", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _same_wording(a: str, b: str) -> bool:
    """Equal apart from case, whitespace and closing punctuation, so adding a
    final period doesn't count as a rewrite."""
    norm = lambda t: re.sub(r"\s+", " ", (t or "").strip().rstrip(".;").lower())
    return norm(a) == norm(b)


# Outcome of one rewrite attempt (stored on ChangeProposal.status).
STATUS_OK = "ok"                            # the LLM produced a changed bullet
STATUS_UNCHANGED = "unchanged"              # the LLM kept the original wording
STATUS_LLM_UNAVAILABLE = "llm_unavailable"  # provider unreachable / misconfigured
STATUS_LLM_ERROR = "llm_error"              # the call failed (rate limit, bad output, ...)
FAILED_STATUSES = (STATUS_LLM_UNAVAILABLE, STATUS_LLM_ERROR)


# Backwards compatibility: expose the old name `RewriteProposal` as an
# alias to the richer `ChangeProposal` model so external callers/tests
# that import from this module continue to work.
RewriteProposal = ChangeProposal


class LLMRewriter:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def rewrite_bullet(
        self,
        original_text: str,
        evidence: List[Evidence],
        jd_requirements: List[str],
        target_keywords: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """Rewrite (or, given a single free-text `original_text` with no
        matching prior bullet, compose) a bullet grounded ONLY in `evidence`.

        Returns (rewritten_text, rationale). Falls back to
        (original_text, "") whenever the LLM is unavailable or the call
        fails — this never fabricates content, it just means no
        improvement was made. Use rewrite_bullet_with_status() to find out why.
        """
        text, rationale, _status, _error = self.rewrite_bullet_with_status(
            original_text, evidence, jd_requirements, target_keywords
        )
        return text, rationale

    def rewrite_bullet_with_status(
        self,
        original_text: str,
        evidence: List[Evidence],
        jd_requirements: List[str],
        target_keywords: Optional[List[str]] = None,
    ) -> Tuple[str, str, str, Optional[str]]:
        """Like rewrite_bullet, plus what happened, so failures are visible
        instead of looking like "no change needed". Returns
        (text, rationale, status, error) where status is one of
        STATUS_OK, STATUS_UNCHANGED, STATUS_LLM_UNAVAILABLE, STATUS_LLM_ERROR."""
        if not self.llm_client or not self.llm_client.is_available():
            reason = getattr(self.llm_client, "last_error", None) if self.llm_client else "no LLM configured"
            return original_text, "", STATUS_LLM_UNAVAILABLE, reason or "LLM unavailable"

        prompt_path = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "rewrite_bullet.txt")
        system_prompt = "You are a precise resume bullet writer."
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()

        evidence_text = "\n".join([f"- ({ev.id}) {ev.text}" for ev in evidence]) or "(none provided)"
        reqs_text = "\n".join([f"- {r}" for r in jd_requirements]) or "(none provided)"

        keywords_block = ""
        if target_keywords:
            keywords_block = (
                "\n\nSpecific JD keywords/phrases to naturally work in, ONLY if genuinely "
                "supported by the evidence above — never force a keyword in if it doesn't fit, "
                "and never claim a skill/tool/metric that isn't present in the evidence:\n"
                + "\n".join(f"- {k}" for k in target_keywords)
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                f"Original Bullet:\n{original_text}\n\n"
                f"Available Source Evidence:\n{evidence_text}\n\n"
                f"Target Job Description Requirements:\n{reqs_text}"
                f"{keywords_block}"
            )},
        ]

        try:
            result = self.llm_client.generate_json(
                messages=messages,
                schema_model=BulletRewriteResult,
                temperature=0.1,
            )
            rewritten = normalize_llm_text(result.rewritten or "")
            if rewritten.startswith("•") or rewritten.startswith("-"):
                rewritten = rewritten.lstrip("•- ").strip()
            if not rewritten or rewritten == original_text.strip():
                return original_text, (result.rationale or "").strip(), STATUS_UNCHANGED, None
            return rewritten, (result.rationale or "").strip(), STATUS_OK, None
        except Exception as e:
            return original_text, "", STATUS_LLM_ERROR, str(e)

    def rewrite_role(
        self,
        exp: Optional[Experience],
        items: List[Dict],
        header: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Dict], Optional[str], str]:
        """Rewrite several bullets of one role in ONE call (P1.4).

        items: [{"bullet_id", "text", "group", "requirements", "keywords",
        "evidence_ids"}]. Returns ({bullet_id: {"text", "keywords_used",
        "status"}}, error, status for any bullet not returned). Bullets the
        call couldn't rewrite keep their text and carry the error, so a
        failure is visible instead of looking like "no change needed"."""
        if not self.llm_client or not self.llm_client.is_available():
            reason = getattr(self.llm_client, "last_error", None) if self.llm_client else "no LLM configured"
            return {}, reason or "LLM unavailable", STATUS_LLM_UNAVAILABLE
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "rewrite_role.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()

        if exp is not None:
            titles = ", ".join(r.title for r in exp.all_roles() if r.title) or "(not given)"
            header = [f"Company: {exp.company or '(not given)'}", f"Titles: {titles}"]
        lines = list(header or []) + ["", "Bullets:"]
        for item in items:
            lines.append(f"- bullet_id: {item['bullet_id']}")
            lines.append(f"  text: {item['text']}")
            if item.get("group"):
                lines.append(f"  sub-heading: {item['group']}")
            lines.append("  closest JD requirements: " + ("; ".join(item["requirements"]) or "(none)"))
            lines.append("  JD keywords it may use: " + (", ".join(item["keywords"]) or "(none)"))
            lines.append("  evidence_ids: " + ", ".join(item["evidence_ids"]))
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(lines)},
        ]
        try:
            result = self.llm_client.generate_json(
                messages=messages, schema_model=RoleRewriteResult, temperature=0.1, effort="medium",
            )
        except Exception as e:
            return {}, str(e), STATUS_LLM_ERROR

        by_id = {item["bullet_id"]: item for item in items}
        out: Dict[str, Dict] = {}
        for bullet in result.bullets:
            item = by_id.get(bullet.bullet_id)
            if item is None or bullet.bullet_id in out:
                continue  # unknown or duplicate id from the model
            text = normalize_llm_text(bullet.rewritten or "").lstrip("•- ").strip()
            allowed = {k.lower() for k in item["keywords"]}
            used = [k for k in bullet.keywords_used if k.lower() in allowed and k.lower() in text.lower()]
            if not text or _same_wording(text, item["text"]):
                out[bullet.bullet_id] = {"text": item["text"], "keywords_used": [], "status": STATUS_UNCHANGED}
            else:
                out[bullet.bullet_id] = {"text": text, "keywords_used": used, "status": STATUS_OK}
        return out, None, STATUS_LLM_ERROR

    def execute_plan(
        self,
        resume: Resume,
        plan: TailoringPlan,
        evidence_list: List[Evidence],
        job_description: JobDescription,
    ) -> List[RewriteProposal]:
        """One LLM call per role (P1.4): all of a job's bullets that the
        planner marked REWRITE go together, so the model sees the whole role
        (no repeated opening verbs, consistent style) and a run stays within
        the free tier's rate limits."""
        proposals: List[RewriteProposal] = []
        req_by_id = {r.id: r.text for r in job_description.requirements}
        actions = {a.source_id: a for a in plan.actions if a.action == "REWRITE"}

        def item_for(b, group):
            action = actions[b.id]
            return {
                "bullet_id": b.id, "text": b.text, "group": group,
                # Only this bullet's closest requirements and the JD
                # keywords it already contains (P1.3).
                "requirements": [req_by_id[i] for i in action.requirement_ids if i in req_by_id],
                "keywords": list(action.keywords),
                "evidence_ids": list(action.evidence_ids),
            }

        def collect(todo, results, error, missing_status):
            for b in todo:
                action = actions[b.id]
                res = results.get(b.id)
                item_error = None
                if res is None:
                    res = {"text": b.text, "keywords_used": [], "status": missing_status}
                    item_error = error or "the model returned no rewrite for this bullet"
                rationale = action.rationale
                if res["keywords_used"]:
                    rationale += f" — worked in: {', '.join(res['keywords_used'])}"
                proposals.append(RewriteProposal(
                    id=f"prop_{uuid4().hex[:8]}",
                    target_semantic_id=b.id,
                    target_source_location_id=b.source_location_id or b.id,
                    original_text=b.text,
                    proposed_text=res["text"],
                    evidence_ids=action.evidence_ids,
                    rationale=rationale,
                    status=res["status"],
                    error=item_error,
                    relevance=action.relevance,
                    target_keywords=list(action.keywords),
                ))

        def rewrite_with_follow_up(exp, items, header=None):
            """One call, plus at most one more for bullets the model skipped
            (it sometimes returns only the first few of a long role)."""
            results, error, missing_status = self.rewrite_role(exp, items, header=header)
            skipped = [i for i in items if i["bullet_id"] not in results]
            if results and skipped and not error:
                more, error, missing_status = self.rewrite_role(exp, skipped, header=header)
                results = {**results, **more}
            return results, error, missing_status

        for exp in resume.experience:
            todo = [b for b in exp.bullets if b.id in actions]
            if todo:
                collect(todo, *rewrite_with_follow_up(exp, [item_for(b, b.group) for b in todo]))

        # All project bullets in one more call (P1.7), each with its
        # project name as the sub-heading.
        project_todo = [(b, p.name) for p in resume.projects for b in p.bullets if b.id in actions]
        if project_todo:
            header = ["Section: Projects (each bullet's sub-heading is its project name)"]
            results = rewrite_with_follow_up(None, [item_for(b, name) for b, name in project_todo], header=header)
            collect([b for b, _ in project_todo], *results)
        return proposals

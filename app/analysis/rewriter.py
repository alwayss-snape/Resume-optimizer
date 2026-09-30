import os
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import Field

from app.analysis.change_proposal import ChangeProposal
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.resume import Resume
from app.domain.tailoring import TailoringAction, TailoringPlan
from app.llm.client import LLMClient
from app.llm.schemas import BulletRewriteResult, MissingRequirementSuggestion


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
            rewritten = (result.rewritten or "").strip()
            if rewritten.startswith("•") or rewritten.startswith("-"):
                rewritten = rewritten.lstrip("•- ").strip()
            if not rewritten or rewritten == original_text.strip():
                return original_text, (result.rationale or "").strip(), STATUS_UNCHANGED, None
            return rewritten, (result.rationale or "").strip(), STATUS_OK, None
        except Exception as e:
            return original_text, "", STATUS_LLM_ERROR, str(e)

    def suggest_for_missing_requirement(
        self,
        requirement_text: str,
        jd_keywords: Optional[List[str]] = None,
    ) -> Optional[MissingRequirementSuggestion]:
        """Advisory only. For a JD requirement the resume doesn't currently
        support, draft ONE example bullet phrasing the candidate could adapt
        IF they actually have matching experience — never inserted into the
        resume automatically, since nothing here is evidence-backed.
        """
        if not self.llm_client or not self.llm_client.is_available():
            return None

        system_prompt = (
            "You help candidates see exactly what a job requirement is looking for. "
            "Given ONE requirement their résumé does not currently address, write a "
            "single example résumé bullet (as if the candidate already had this "
            "experience) that a strong, ATS-friendly résumé for this exact requirement "
            "might contain. Naturally use the requirement's own terminology and any "
            "relevant keywords supplied so the phrasing would parse well against an "
            "ATS keyword scan. This is a template for the candidate to adapt with their "
            "own real facts, evidence, and numbers — it must read as an illustrative "
            "example, not as a factual claim about the candidate. Keep it to one "
            "concise sentence (8-25 words)."
        )
        keywords_text = "\n".join(f"- {k}" for k in (jd_keywords or [])) or "(none provided)"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                f"Missing requirement:\n{requirement_text}\n\n"
                f"Job description keywords (use only the ones relevant to this "
                f"requirement):\n{keywords_text}"
            )},
        ]
        try:
            result = self.llm_client.generate_json(
                messages=messages,
                schema_model=MissingRequirementSuggestion,
                temperature=0.2,
            )
            if not (result.suggested_phrasing or "").strip():
                return None
            result.requirement_text = requirement_text
            return result
        except Exception:
            return None

    def execute_plan(
        self,
        resume: Resume,
        plan: TailoringPlan,
        evidence_list: List[Evidence],
        job_description: JobDescription,
    ) -> List[RewriteProposal]:
        proposals: List[RewriteProposal] = []
        evidence_map = {ev.id: ev for ev in evidence_list}

        # Build bullet map
        bullet_map = {}
        for exp in resume.experience:
            for bullet in exp.bullets:
                bullet_map[bullet.id] = bullet

        for action in plan.actions:
            if action.action == "REWRITE" and action.source_id in bullet_map:
                bullet = bullet_map[action.source_id]
                orig_text = bullet.text
                action_ev = [evidence_map[ev_id] for ev_id in action.evidence_ids if ev_id in evidence_map]
                jd_req_texts = [r.text for r in job_description.requirements]

                new_text, llm_rationale, status, error = self.rewrite_bullet_with_status(
                    orig_text,
                    action_ev,
                    jd_req_texts,
                    target_keywords=job_description.keywords,
                )

                # Combine the planner's "why this bullet was picked" rationale
                # with the LLM's own explanation of what it changed and why,
                # so the review UI can show the candidate both which JD
                # requirement/keywords this targets and what changed.
                combined_rationale = action.rationale
                if llm_rationale:
                    combined_rationale = f"{action.rationale} — {llm_rationale}"

                # Prefer the bullet's raw source_location_id for patching; fall back to semantic id
                proposals.append(RewriteProposal(
                    id=f"prop_{uuid4().hex[:8]}",
                    target_semantic_id=bullet.id,
                    target_source_location_id=bullet.source_location_id or bullet.id,
                    original_text=orig_text,
                    proposed_text=new_text,
                    evidence_ids=action.evidence_ids,
                    rationale=combined_rationale,
                    status=status,
                    error=error,
                ))

        return proposals

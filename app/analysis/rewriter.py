import os
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import Field

from app.analysis.change_proposal import ChangeProposal
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.resume import Resume
from app.domain.tailoring import TailoringAction, TailoringPlan
from app.llm.client import LLMClient


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
    ) -> str:
        if not self.llm_client or not self.llm_client.is_available():
            # Deterministic fallback: return original text if LLM unavailable
            return original_text

        prompt_path = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "rewrite_bullet.txt")
        system_prompt = "You are a precise resume bullet writer."
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()

        evidence_text = "\n".join([f"- {ev.text}" for ev in evidence])
        reqs_text = "\n".join([f"- {r}" for r in jd_requirements])

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                f"Original Bullet:\n{original_text}\n\n"
                f"Available Source Evidence:\n{evidence_text}\n\n"
                f"Target Job Description Requirements:\n{reqs_text}\n\n"
                f"Output ONLY the single rewritten bullet string."
            )},
        ]

        try:
            resp = self.llm_client.generate(messages=messages, temperature=0.1)
            rewritten = resp.raw_text.strip()
            if rewritten.startswith("•") or rewritten.startswith("-"):
                rewritten = rewritten.lstrip("•- ").strip()
            return rewritten if rewritten else original_text
        except Exception:
            return original_text

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

                new_text = self.rewrite_bullet(orig_text, action_ev, jd_req_texts)
                # Prefer the bullet's raw source_location_id for patching; fall back to semantic id
                proposals.append(RewriteProposal(
                    id=f"prop_{uuid4().hex[:8]}",
                    target_semantic_id=bullet.id,
                    target_source_location_id=bullet.source_location_id or bullet.id,
                    original_text=orig_text,
                    proposed_text=new_text,
                    evidence_ids=action.evidence_ids,
                    rationale=action.rationale,
                ))

        return proposals

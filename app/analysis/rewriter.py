import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.resume import Resume
from app.domain.tailoring import TailoringAction, TailoringPlan
from app.llm.client import LLMClient

class RewriteProposal(BaseModel):
    source_id: str
    original_text: str
    rewritten_text: str
    evidence_ids: List[str] = Field(default_factory=list)
    rationale: str = ""

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
                bullet_map[bullet.id] = bullet.text

        for action in plan.actions:
            if action.action == "REWRITE" and action.source_id in bullet_map:
                orig_text = bullet_map[action.source_id]
                action_ev = [evidence_map[ev_id] for ev_id in action.evidence_ids if ev_id in evidence_map]
                jd_req_texts = [r.text for r in job_description.requirements]

                new_text = self.rewrite_bullet(orig_text, action_ev, jd_req_texts)
                proposals.append(RewriteProposal(
                    source_id=action.source_id,
                    original_text=orig_text,
                    rewritten_text=new_text,
                    evidence_ids=action.evidence_ids,
                    rationale=action.rationale,
                ))

        return proposals

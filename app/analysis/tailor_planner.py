from typing import List, Optional
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.report import Match
from app.domain.resume import Resume
from app.domain.tailoring import TailoringAction, TailoringPlan
from app.llm.client import LLMClient

class TailoringPlanner:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def create_plan(
        self,
        resume: Resume,
        job_description: JobDescription,
        evidence_list: List[Evidence],
        matches: List[Match],
    ) -> TailoringPlan:
        actions: List[TailoringAction] = []
        unsupported: List[str] = []

        match_by_id = {m.requirement_id: m for m in matches}
        evidence_by_id = {ev.id: ev for ev in evidence_list}

        # Track missing requirements
        for match in matches:
            if match.status == "MISSING":
                unsupported.append(match.requirement_text)

        # Plan actions for experience bullets
        for exp in resume.experience:
            for bullet in exp.bullets:
                # Find evidence corresponding to bullet
                bullet_ev = [ev for ev in evidence_list if ev.source_id == bullet.id]
                bullet_ev_ids = [ev.id for ev in bullet_ev]

                # Check if bullet matches any JD requirement
                matched_reqs = [
                    m for m in matches
                    if set(m.evidence_ids).intersection(bullet_ev_ids)
                ]

                if matched_reqs:
                    actions.append(TailoringAction(
                        action="REWRITE",
                        source_id=bullet.id,
                        target_section="experience",
                        evidence_ids=bullet_ev_ids,
                        rationale=f"Align bullet with JD requirement: {matched_reqs[0].requirement_text}",
                    ))
                else:
                    actions.append(TailoringAction(
                        action="KEEP",
                        source_id=bullet.id,
                        target_section="experience",
                        evidence_ids=bullet_ev_ids,
                        rationale="Maintain original bullet text as standard experience.",
                    ))

        return TailoringPlan(
            actions=actions,
            unsupported_requirements=unsupported,
        )

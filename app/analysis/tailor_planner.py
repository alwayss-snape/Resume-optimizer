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
                    # A SEMANTIC_PARTIAL match is a weaker, inferred (paraphrase)
                    # signal compared to EXPLICIT/SUPPORTED/PARTIAL, which are
                    # backed by exact or token-overlap evidence. When a bullet's
                    # only match is semantic, it's still correct to select it
                    # for REWRITE (tightening a genuinely relevant bullet toward
                    # the JD's phrasing, grounded in the same real evidence) —
                    # but the rationale must say so plainly, rather than present
                    # it as an exact requirement match when it wasn't one.
                    deterministic_matches = [m for m in matched_reqs if m.status != "SEMANTIC_PARTIAL"]
                    primary_match = deterministic_matches[0] if deterministic_matches else matched_reqs[0]
                    is_semantic_only = not deterministic_matches

                    if is_semantic_only:
                        rationale = (
                            f"Align bullet with JD requirement (inferred via semantic "
                            f"similarity, not an exact match): {primary_match.requirement_text}"
                        )
                    else:
                        rationale = f"Align bullet with JD requirement: {primary_match.requirement_text}"

                    actions.append(TailoringAction(
                        action="REWRITE",
                        source_id=bullet.id,
                        target_section="experience",
                        evidence_ids=bullet_ev_ids,
                        rationale=rationale,
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

    def rank_missing_requirements(
        self,
        missing_matches: List[Match],
        job_description: JobDescription,
        limit: int = 5,
    ) -> List[Match]:
        """Order MISSING matches so the most important, still-unaddressed
        requirements surface first (required before preferred before
        informational), for driving advisory "what to add" suggestions.
        """
        priority_by_req = {r.id: r.priority for r in job_description.requirements}
        priority_rank = {"required": 0, "preferred": 1, "informational": 2}

        def sort_key(m: Match):
            return priority_rank.get(priority_by_req.get(m.requirement_id, "preferred"), 1)

        ranked = sorted(missing_matches, key=sort_key)
        return ranked[:limit]

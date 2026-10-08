import math
from typing import Callable, Dict, List, Optional, Sequence

from app.analysis.keyword_match import KeywordMatcher, tokens
from app.analysis.project_select import apply_to_plan, jd_is_thin, select_projects
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.report import Match
from app.domain.resume import Resume
from app.domain.tailoring import TailoringAction, TailoringPlan
from app.llm.client import LLMClient

Embedder = Callable[[Sequence[str]], List[Sequence[float]]]

# Words that carry no signal when comparing a bullet with a requirement.
_FILLER = {
    "and", "the", "with", "for", "to", "of", "in", "on", "a", "an", "or", "by", "as", "at", "from", "into",
    "using", "use", "such", "like", "e.g", "eg", "experience", "strong", "ability", "work", "working", "team",
    "teams", "including", "across", "through", "their", "our", "your", "we", "you", "be", "is", "are",
}
MIN_RELEVANCE = 0.15      # below this a bullet is kept as-is (and is a trim candidate)
MAX_REQUIREMENTS = 3      # requirements sent to the rewriter per bullet
DETERMINISTIC_MATCH_BONUS = 0.2


def _content(text: str) -> set:
    return {t for t in tokens(text) if t not in _FILLER and len(t) > 1}


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class TailoringPlanner:
    """Planner v2 (P1.3): scores every experience bullet for relevance to the
    JD, rewrites all relevant ones (not only those that matched a
    requirement), gives each rewrite only its closest requirements and the
    JD keywords it may use, orders bullets by relevance within each
    sub-heading, and marks the least relevant as trim candidates."""

    def __init__(self, llm_client: Optional[LLMClient] = None, embedder: Optional[Embedder] = None):
        self.llm_client = llm_client
        self.embedder = embedder  # sentence embeddings when available; token overlap otherwise
        self.keyword_matcher = KeywordMatcher()

    def _similarities(self, bullets: List[str], requirements: List[str]) -> List[List[float]]:
        """bullets x requirements similarity in 0..1."""
        if not bullets or not requirements:
            return [[0.0] * len(requirements) for _ in bullets]
        if self.embedder is not None:
            try:
                vectors = self.embedder(list(bullets) + list(requirements))
                b_vecs, r_vecs = vectors[:len(bullets)], vectors[len(bullets):]
                return [[max(0.0, float(_cosine(b, r))) for r in r_vecs] for b in b_vecs]
            except Exception:
                pass  # fall back to token overlap
        req_sets = [_content(r) for r in requirements]
        sims = []
        for b in bullets:
            b_set = _content(b)
            sims.append([len(b_set & r) / len(r) if r else 0.0 for r in req_sets])
        return sims

    def create_plan(
        self,
        resume: Resume,
        job_description: JobDescription,
        evidence_list: List[Evidence],
        matches: List[Match],
        brief=None,
    ) -> TailoringPlan:
        unsupported = [m.requirement_text for m in matches if m.status == "MISSING"]
        requirements = job_description.requirements
        keyword_rows = [r for r in self.keyword_matcher.match(job_description, resume).rows if r.kind != "title"]

        entries = []  # (section, bullet, evidence ids, context text)
        for exp in resume.experience:
            for bullet in exp.bullets:
                ev_ids = [ev.id for ev in evidence_list if ev.source_id == bullet.id]
                entries.append(("experience", bullet, ev_ids, f"{bullet.group or ''} {bullet.text}"))
        # Project bullets go through the same flow (P1.7); the project name
        # is their context, like a sub-heading inside a job.
        for proj in resume.projects:
            for bullet in proj.bullets:
                ev_ids = [ev.id for ev in evidence_list if ev.source_id == bullet.id]
                entries.append(("projects", bullet, ev_ids, f"{proj.name} {bullet.text}"))

        sims = self._similarities([e[1].text for e in entries], [r.text for r in requirements])

        # Keywords already in each bullet (or its sub-heading), weighted.
        bullet_keywords: List[List[str]] = []
        keyword_weight: List[float] = []
        for _, _, _, context in entries:
            section = [("bullet", tokens(context))]
            found = []
            weight = 0.0
            for row in keyword_rows:
                # Same lookup as the match rate (aliases, plurals, PySpark -> Spark).
                if self.keyword_matcher._find(row.keyword, section):
                    found.append(row.keyword)
                    weight += row.weight
            bullet_keywords.append(found)
            keyword_weight.append(weight)
        max_weight = max(keyword_weight, default=0.0) or 1.0

        actions: List[TailoringAction] = []
        for idx, (section_name, bullet, ev_ids, _) in enumerate(entries):
            matched = [m for m in matches if set(m.evidence_ids) & set(ev_ids) and m.status != "MISSING"]
            deterministic = [m for m in matched if m.status != "SEMANTIC_PARTIAL"]
            ranked_reqs = sorted(range(len(requirements)), key=lambda j: -sims[idx][j])
            top_reqs = [j for j in ranked_reqs[:MAX_REQUIREMENTS] if sims[idx][j] > 0]
            best_sim = sims[idx][ranked_reqs[0]] if ranked_reqs else 0.0

            relevance = 0.5 * (keyword_weight[idx] / max_weight) + 0.5 * best_sim
            if deterministic:
                relevance += DETERMINISTIC_MATCH_BONUS
            relevance = round(float(min(1.0, relevance)), 3)

            requirement_ids = [m.requirement_id for m in deterministic or matched]
            requirement_ids += [requirements[j].id for j in top_reqs if requirements[j].id not in requirement_ids]
            requirement_ids = requirement_ids[:MAX_REQUIREMENTS]

            if matched:
                # A SEMANTIC_PARTIAL match is an inferred (paraphrase) signal;
                # the rationale says so rather than presenting it as exact.
                primary = (deterministic or matched)[0]
                if deterministic:
                    rationale = f"Align bullet with JD requirement: {primary.requirement_text}"
                else:
                    rationale = (f"Align bullet with JD requirement (inferred via semantic similarity, "
                                 f"not an exact match): {primary.requirement_text}")
            elif top_reqs:
                rationale = f"Relevant to JD requirement: {requirements[top_reqs[0]].text}"
            else:
                rationale = "Relevant to the JD's keywords."
            if bullet_keywords[idx]:
                rationale += f" (JD keywords here: {', '.join(bullet_keywords[idx][:5])})"

            rewrite = bool(matched) or relevance >= MIN_RELEVANCE
            actions.append(TailoringAction(
                action="REWRITE" if rewrite else "KEEP",
                source_id=bullet.id,
                target_section=section_name,
                evidence_ids=ev_ids,
                rationale=rationale if rewrite else "Not relevant to this JD; kept as written.",
                relevance=relevance,
                requirement_ids=requirement_ids,
                keywords=bullet_keywords[idx],
                trim_candidate=relevance < MIN_RELEVANCE,
            ))

        # Most relevant first within each sub-heading; sub-headings keep
        # their order so a project's bullets stay together.
        relevance_by_id = {a.source_id: a.relevance for a in actions}
        bullet_order: Dict[str, List[str]] = {}
        for exp in resume.experience:
            ordered: List[str] = []
            for _, group_bullets in exp.bullet_groups():
                ordered += [b.id for b in sorted(group_bullets, key=lambda b: -relevance_by_id.get(b.id, 0.0))]
            bullet_order[exp.id] = ordered
        for proj in resume.projects:
            bullet_order[proj.id] = [b.id for b in sorted(proj.bullets, key=lambda b: -relevance_by_id.get(b.id, 0.0))]

        plan = TailoringPlan(actions=actions, unsupported_requirements=unsupported, bullet_order=bullet_order,
                             ranked_by_impact=jd_is_thin(job_description))
        # Choose projects, not lines (P10.13): a job keeps its best 2-3 projects.
        # P11.4: with a role brief, projects are chosen to cover its competencies;
        # a project's notes from the owner's project bank (P11.1) count too.
        notes: Dict[str, List[str]] = {}
        for ev in evidence_list:
            if "::" in (ev.source_id or ""):
                notes.setdefault(ev.source_id, []).append(ev.text)
        apply_to_plan(plan, select_projects(resume, actions, job_description, embedder=self.embedder, brief=brief,
                                            notes=notes), resume, job_description, self.embedder)
        if brief is not None and getattr(brief, "source", "") == "llm":
            plan.ranked_by_impact = False  # the brief gives the job's needs, however short the post
        return plan

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

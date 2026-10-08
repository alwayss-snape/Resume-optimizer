"""Choose projects, not lines (P10.13).

A job with several projects under it (bullets with a `group`, e.g. a
"Fraud Detection Framework" sub-heading) keeps its 2-3 best projects instead of every
one. "Best" is relevance to the JD; when the JD is too thin to rank by (a
two-sentence LinkedIn post) it's impact, read from the bullets by rules, never
by the LLM, so the reason can be shown and the user can override it on Review.
Projects left out stay listed there as "not used".
"""
import re
from typing import Dict, List, Optional, Sequence

from app.domain.job import JobDescription
from app.domain.resume import Experience, Resume
from app.domain.tailoring import ProjectChoice, TailoringAction
from app.analysis.experience import is_ongoing

CURRENT_JOB_PROJECTS = 3   # projects kept for the current job
OLDER_JOB_PROJECTS = 2     # and for each older one
BULLETS_PER_PROJECT = 3    # a chosen project's extra bullets become trim candidates
THIN_JD_KEYWORDS = 3       # a JD naming fewer skills than this ranks projects by impact

# Shipped work, not the word "production" alone ("monitor production pipelines").
_PRODUCTION = re.compile(r"\b(?:in|into|to) production\b|\bproduction[- ](?:grade|scoring|system|model|"
                         r"pipeline|deployment)s?\b|\b(?:deployed|launched|shipped|rolled out|went live|go-live|"
                         r"replac(?:ed|ing)|moderni[sz]ed|automat(?:ed|ing))\b", re.I)
_OUTCOME = re.compile(r"\b(?:reduc\w*|cut|cutting|sav(?:ed|ing)|increas\w*|improv\w*|boost\w*|"
                      r"accelerat\w*|grew|faster)\b", re.I)
_RECOGNITION = re.compile(r"\b(?:won|winner|award\w*|hackathon|recogni[sz]ed|patent\w*)\b", re.I)
_EARLY = re.compile(r"\b(?:concept|exploring|explor(?:ed|ation)|pilot\w*|prototype|poc|proof of concept|"
                    r"working on|ideat\w*|design stage)\b", re.I)
# "12M users", "2.3B rows", "500K+", "60%", "1,000-job": numbers that show size or results.
_SCALE = re.compile(r"\b\d[\d,.]*\s*(?:[KMB]\b|\+|%|million|billion|thousand)|\b\d{1,3}(?:,\d{3})+\b"
                    r"|\b\d{4,}\b(?!\s*(?:–|-|to)\s*\d{2,4})", re.I)
_YEAR = re.compile(r"^(?:19|20)\d{2}$")


def jd_is_thin(job_desc: JobDescription) -> bool:
    """Too little to rank by: a short post can still name its skills ("pricing,
    yield optimization and inventory management"), so count those, not lines."""
    return len(_fit_keywords(job_desc)) < THIN_JD_KEYWORDS


def _fit_keywords(job_desc: JobDescription) -> List[str]:
    title = (job_desc.job_title or "").lower()
    return [k for k in job_desc.keywords if k and k.lower() not in title and k.lower() != "data"]


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = sum(x * x for x in a) ** 0.5, sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def keyword_fit(groups: Sequence[Sequence[str]], keywords: Sequence[str], embedder) -> List[tuple]:
    """How close each project is to the JD's skills, one skill at a time: the
    best of its lines for each keyword, averaged. A whole requirement
    sentence buries "inventory management" among filler words; one keyword
    at a time, demand forecasting reads as near it. Returns (fit, the two
    nearest keywords) per project; (0, []) without embeddings."""
    if embedder is None or not keywords or not groups:
        return [(0.0, [])] * len(groups)
    texts = [t for g in groups for t in g]
    try:
        vectors = embedder(list(keywords) + texts)
    except Exception:
        return [(0.0, [])] * len(groups)
    k_vecs, t_vecs = vectors[:len(keywords)], vectors[len(keywords):]
    out, i = [], 0
    for g in groups:
        rows = t_vecs[i:i + len(g)]
        i += len(g)
        best = [max(_cosine(r, k) for r in rows) for k in k_vecs]
        nearest = [kw for _, kw in sorted(zip(best, keywords), key=lambda x: -x[0])[:2]]
        out.append((sum(best) / len(best), nearest))
    return out


def _scale_terms(text: str) -> List[str]:
    found = []
    for m in _SCALE.finditer(text):
        term = m.group(0).strip()
        if _YEAR.match(term.rstrip("+")):
            continue  # "2024" is a date, not a size
        found.append(term)
    return found


def _early(texts: Sequence[str]):
    """An early-stage word in the project's bullets, not in a name: "Route
    Pilot" is a product, "piloting a global model" is early stage. The
    project's heading (texts[0]) is a name, so it never counts."""
    for text in texts[1:]:
        for m in _EARLY.finditer(text):
            word = m.group(0)
            if word[0].isupper() and m.start() > 0 and text[m.start() - 2:m.start()].strip() not in (".", ";", ":"):
                continue  # a capitalised word mid-sentence: a name
            return m
    return None


def impact(texts: Sequence[str]) -> tuple:
    """(0-1 score, the signals that gave it), from the project's own words.
    Numbers count once there are two of them; more don't add, so the biggest
    figure doesn't win by itself."""
    text = " ".join(texts)
    scale = _scale_terms(text)
    production = bool(_PRODUCTION.search(text))
    outcome = bool(_OUTCOME.search(text))
    recognition = bool(_RECOGNITION.search(text))
    early = _early(texts)
    score = (0.35 * production + 0.25 * min(1.0, len(scale) / 2) + 0.2 * outcome
             + 0.35 * recognition - 0.2 * bool(early))
    signals = []
    if recognition:
        signals.append("an award or win")
    if production:
        signals.append("in production")
    if scale:
        signals.append("scale or results (" + ", ".join(scale[:2]) + ")")
    elif outcome:
        signals.append("a measured outcome")
    if early:
        signals.append(f"early stage (\"{early.group(0).lower()}\")")
    return round(max(0.0, min(1.0, score)), 3), signals


def _job_label(exp: Experience) -> str:
    return " — ".join(v for v in (exp.company, exp.title) if v) or exp.id


def _is_current(exp: Experience, index: int) -> bool:
    roles = exp.all_roles()
    return index == 0 or bool(roles and is_ongoing(roles[0].end_date))


def select_projects(resume: Resume, actions: Sequence[TailoringAction], job_desc: JobDescription,
                    embedder=None) -> List[ProjectChoice]:
    """Every project of every job with more projects than it keeps, chosen
    or not, with the reason. Jobs with flat bullets, or few enough projects,
    aren't listed: nothing to choose there."""
    by_id: Dict[str, TailoringAction] = {a.source_id: a for a in actions if a.source_id}
    thin = jd_is_thin(job_desc)
    choices: List[ProjectChoice] = []
    for index, exp in enumerate(resume.experience):
        groups = [(name, bullets) for name, bullets in exp.bullet_groups() if name]
        limit = CURRENT_JOB_PROJECTS if _is_current(exp, index) else OLDER_JOB_PROJECTS
        if len(groups) <= limit:
            continue
        scored = []
        fits = keyword_fit([[name, *(b.text for b in bullets)] for name, bullets in groups],
                           _fit_keywords(job_desc), embedder)
        top_fit = max(f for f, _ in fits) or 1.0
        for (name, bullets), (fit, nearest) in zip(groups, fits):
            rel = sorted((by_id[b.id].relevance for b in bullets if b.id in by_id), reverse=True)
            relevance = sum(rel[:2]) / len(rel[:2]) if rel else 0.0
            # The bullets' own relevance, and how near the project is to each JD skill (scaled within the job).
            relevance = round(0.4 * relevance + 0.6 * fit / top_fit if top_fit and any(f for f, _ in fits)
                              else relevance, 3)
            imp, signals = impact([name, *(b.text for b in bullets)])
            keywords = list(nearest)  # the JD skills it's nearest to, then the ones it names
            for b in bullets:
                for k in (by_id[b.id].keywords if b.id in by_id else []):
                    if k not in keywords:
                        keywords.append(k)
            score = 0.7 * imp + 0.3 * relevance if thin else 0.75 * relevance + 0.25 * imp
            scored.append((score, name, bullets, relevance, imp, signals, [k for k in keywords if k.lower() != "data"]))
        ranked = sorted(scored, key=lambda s: -s[0])
        kept = {s[1] for s in ranked[:limit]}
        for score, name, bullets, relevance, imp, signals, keywords in scored:  # file order
            chosen = name in kept
            if thin:
                why = ", ".join(signals) if signals else "no clear signs of impact in its wording"
                reason = (f"High impact: {why}" if chosen else f"Lower impact than the projects kept: {why}")
            elif chosen:
                reason = (f"Closest to the job (nearest job skills: {', '.join(keywords[:3])})" if keywords
                          else "Closest to the job")
            else:
                reason = "Less relevant to this job than the projects kept" + (
                    f" (nearest job skills: {', '.join(keywords[:2])})" if keywords else "")
            choices.append(ProjectChoice(
                key=f"{exp.id}::{name}", experience_id=exp.id, job=_job_label(exp), name=name,
                bullet_ids=[b.id for b in bullets], chosen=chosen, reason=reason,
                relevance=relevance, impact=imp))
    return choices


def apply_to_plan(plan, choices: Sequence[ProjectChoice], resume: Resume, job_desc: Optional[JobDescription] = None,
                  embedder=None) -> None:
    """Bullets of a project left out aren't rewritten (no LLM call). A kept
    project's bullets are all polished (tight, ATS-plain wording), whatever
    their relevance, and scored one by one on the JD's skills and their
    impact: the weakest go first in page-fit, and sit last in the project.
    Past the first few they're trim candidates."""
    by_id = {a.source_id: a for a in plan.actions if a.source_id}
    texts = {b.id: b.text for e in resume.experience for b in e.bullets}
    keywords = _fit_keywords(job_desc) if job_desc is not None else []
    for c in choices:
        if not c.chosen:
            for bid in c.bullet_ids:
                a = by_id.get(bid)
                if a:
                    a.action, a.rationale, a.trim_candidate = "KEEP", f"Project left out: {c.reason}", True
            continue
        ids = [b for b in c.bullet_ids if b in by_id]
        fits = keyword_fit([[texts.get(b, "")] for b in ids], keywords, embedder)
        top = max((f for f, _ in fits), default=0.0) or 1.0
        for bid, (fit, _) in zip(ids, fits):
            a = by_id[bid]
            a.relevance = round(min(1.0, 0.4 * a.relevance + 0.4 * fit / top + 0.2 * impact(["", texts.get(bid, "")])[0]), 3)
            if a.action != "REWRITE":
                a.action = "REWRITE"
                a.rationale = f"Polished for a project kept for this job ({c.name})."
        for bid in sorted(ids, key=lambda b: -by_id[b].relevance)[BULLETS_PER_PROJECT:]:
            by_id[bid].trim_candidate = True
    # Bullet order follows the new scores, still project by project.
    for exp in resume.experience:
        if exp.id in plan.bullet_order:
            order = []
            for _, group_bullets in exp.bullet_groups():
                order += [b.id for b in sorted(group_bullets, key=lambda b: -(by_id[b.id].relevance if b.id in by_id else 0.0))]
            plan.bullet_order[exp.id] = order
    plan.projects = list(choices)


def left_out_ids(choices: Sequence[ProjectChoice], left_out: Optional[Sequence[str]]) -> List[str]:
    """Bullet ids to leave out: the user's choice (project keys) when given,
    otherwise the projects not chosen."""
    keys = set(left_out) if left_out is not None else {c.key for c in choices if not c.chosen}
    return [b for c in choices if c.key in keys for b in c.bullet_ids]


def remove_bullets(resume: Resume, bullet_ids: Sequence[str]) -> List[str]:
    """Take the left-out bullets off the resume; returns their text (and the
    headings of projects now empty), so coverage counts them as chosen, not lost."""
    gone = set(bullet_ids)
    removed: List[str] = []
    for exp in resume.experience:
        before = {b.group for b in exp.bullets if b.group}
        removed += [b.text for b in exp.bullets if b.id in gone]
        exp.bullets = [b for b in exp.bullets if b.id not in gone]
        removed += sorted(before - {b.group for b in exp.bullets if b.group})
    return removed


MAX_HEADING_WORDS = 6
_HEADING_GLUE = {"and", "&", "for", "of", "the", "with", "in", "on", "a", "an", "to", "-", "/", "+", "via"}


def _stem(word: str) -> str:
    return word[:5] if len(word) > 5 else word


def heading_problem(heading: str, sources: Sequence[str]) -> Optional[str]:
    """Why a proposed project heading can't be used, or None. Every word must
    come from the old heading or the project's bullets (a word's form may
    change: forecast -> Forecasting); at most MAX_HEADING_WORDS words; no figures."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.'-]*|\d[\w.,%+]*|&", heading or "")
    if not words:
        return "the heading is empty"
    if len(words) > MAX_HEADING_WORDS:
        return f"over {MAX_HEADING_WORDS} words"
    if any(w[0].isdigit() for w in words):
        return "figures belong in the bullets"
    known = {_stem(w.lower().strip(".'-")) for t in sources for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.'-]*", t)}
    new = [w for w in words if w.lower() not in _HEADING_GLUE and _stem(w.lower().strip(".'-")) not in known]
    return f"uses words not in your text: {', '.join(new)}" if new else None

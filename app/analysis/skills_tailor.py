"""Skills tailoring (P1.6), deterministic: no LLM, nothing added.

The JD's skills move to the front of each category (and the category with
the most JD skills moves to the top), and a skill is renamed to the JD's
spelling only when it is the same term ("Numpy" -> "NumPy", an alias like
"machine learning" -> "ML"). A related but different term (PySpark vs
Spark) keeps its own name.
"""
import re
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.analysis.change_proposal import ChangeProposal
from app.analysis.keyword_match import KeywordMatcher, tokens
from app.domain.report import KeywordMatchReport
from app.domain.resume import Resume

SKILLS_TARGET = "skills"


def format_skills(skills: Dict[str, List[str]]) -> str:
    """One "Category: a, b, c" line per category (the editable form)."""
    return "\n".join(f"{cat}: {', '.join(items)}" for cat, items in skills.items())


def parse_skills(text: str) -> Dict[str, List[str]]:
    """Inverse of format_skills; a line without a label goes under "Skills"."""
    skills: Dict[str, List[str]] = {}
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        cat, _, items = line.partition(":") if ":" in line else ("Skills", "", line)
        values = [v.strip() for v in re.split(r",(?![^()]*\))", items) if v.strip()]
        if values:
            skills.setdefault(cat.strip() or "Skills", []).extend(values)
    return skills


def _key(term: str) -> str:
    return " ".join(tokens(term))


class SkillsTailor:
    def tailor(self, skills: Dict[str, List[str]], report: KeywordMatchReport) -> Dict[str, List[str]]:
        rows = [r for r in report.rows if r.kind in ("hard", "certification", "soft")]
        spelling: Dict[str, str] = {}
        for r in rows:
            spelling.setdefault(_key(r.keyword), r.keyword)

        matcher = KeywordMatcher()

        def score(item: str) -> Tuple[float, int]:
            # Same lookup as the match rate, so PySpark ranks as the JD's
            # "Spark" (it satisfies it) even though it keeps its own name.
            section = [("skill", tokens(item))]
            best = (0.0, 0)
            for r in rows:
                if matcher._find(r.keyword, section):
                    best = max(best, (r.weight, r.jd_count))
            return best

        tailored: Dict[str, List[str]] = {}
        for cat, items in skills.items():
            renamed = [spelling.get(_key(i), i) for i in items]
            order = sorted(range(len(renamed)), key=lambda i: (-score(items[i])[0], -score(items[i])[1], i))
            tailored[cat] = [renamed[i] for i in order]
        cat_weight = {cat: sum(score(i)[0] for i in items) for cat, items in skills.items()}
        cats = sorted(skills, key=lambda c: (-cat_weight[c], list(skills).index(c)))
        return {c: tailored[c] for c in cats}

    def propose(self, resume: Resume, report: KeywordMatchReport) -> Optional[ChangeProposal]:
        """A skills proposal, or None when nothing would change."""
        if not resume.skills:
            return None
        new = self.tailor(resume.skills, report)
        if new == resume.skills and list(new) == list(resume.skills):
            return None
        moved = [r.keyword for r in report.rows if r.found and r.kind == "hard"
                 and any(_key(r.keyword) == _key(i) for items in resume.skills.values() for i in items)]
        return ChangeProposal(
            id=f"prop_{uuid4().hex[:8]}", target_semantic_id=SKILLS_TARGET, target_source_location_id=SKILLS_TARGET,
            kind="skills", original_text=format_skills(resume.skills), proposed_text=format_skills(new),
            rationale="Skills reordered so the JD's come first" + (f": {', '.join(moved[:6])}" if moved else ""),
            status="ok", validation="PASS",
        )


def unknown_skills(original: Dict[str, List[str]], proposed: Dict[str, List[str]]) -> List[str]:
    """Skills in `proposed` that aren't in `original` under any spelling."""
    known = {_key(i) for items in original.values() for i in items}
    return [i for items in proposed.values() for i in items if _key(i) not in known]


# ---------------------------------------------------------------------------
# Placing a skill the user confirmed (P9.12)
#
# A ticked gap keyword used to join the first category named like "tools /
# frameworks / skills": "ci", "LLMs" and even "Fast learner" ended up under
# "Frameworks". Each skill now goes under a category of its own type, a trait
# is never a skill, and the JD's spelling is kept ("CI", not "ci").
# ---------------------------------------------------------------------------

_TYPE_TERMS = {
    "language": {"python", "java", "javascript", "typescript", "scala", "kotlin", "c", "c++", "c#", "go", "golang",
                 "rust", "ruby", "php", "r", "sql", "nosql", "bash", "shell", "perl", "matlab", "sas", "swift",
                 "objective-c", "haskell", "elixir", "clojure", "julia", "html", "css", "pyspark", "spark sql",
                 "t-sql", "pl/sql", "vba"},
    "framework": {"pandas", "numpy", "scipy", "scikit-learn", "sklearn", "pytorch", "tensorflow", "keras",
                  "xgboost", "lightgbm", "catboost", "statsmodels", "matplotlib", "seaborn", "plotly", "langchain",
                  "llamaindex", "hugging face", "transformers", "spacy", "nltk", "opencv", "react", "angular", "vue",
                  "vue.js", "next.js", "node.js", "express", "django", "flask", "fastapi", "spring", "spring boot",
                  "rails", ".net", "redux", "jest", "pytest", "junit", "selenium", "cypress", "spark", "faiss"},
    "tool": {"mysql", "postgresql", "postgres", "sql server", "ssms", "oracle", "mongodb", "redis", "cassandra",
             "dynamodb", "elasticsearch", "snowflake", "bigquery", "redshift", "aws redshift", "databricks",
             "hadoop", "hive", "kafka", "airflow", "dbt", "mlflow", "kubeflow", "tableau", "power bi", "looker",
             "excel", "powerpoint", "jupyter", "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "terraform",
             "ansible", "jenkins", "github", "gitlab", "github actions", "jira", "confluence", "figma", "linux",
             "git", "sagemaker", "vertex ai", "salesforce", "netsuite", "quickbooks", "sap", "epic", "cerner"},
    "practice": {"ci", "cd", "ci/cd", "continuous integration", "continuous delivery", "continuous deployment",
                 "version control", "unit tests", "unit testing", "testing", "test automation", "tdd", "code review",
                 "code reviews", "agile", "scrum", "kanban", "devops", "mlops", "a/b testing", "experimentation",
                 "microservices", "rest apis", "api design", "etl", "elt", "data modeling", "data modelling",
                 "feature engineering", "model deployment", "model monitoring", "documentation"},
    "expertise": {"llm", "llms", "large language models", "genai", "generative ai", "nlp",
                  "natural language processing", "machine learning", "ml", "deep learning", "computer vision",
                  "statistics", "statistical modeling", "time series", "forecasting", "recommendation systems",
                  "reinforcement learning", "data analysis", "data visualization", "optimization", "ai",
                  "artificial intelligence", "predictive modeling", "causal inference", "rag"},
}

# The category names each type may go under, and the name a new one gets.
_TYPE_CATEGORY_RE = {
    "language": re.compile(r"language", re.IGNORECASE),
    "framework": re.compile(r"framework|librar|package", re.IGNORECASE),
    "tool": re.compile(r"tool|platform|software|cloud|database|technolog|stack", re.IGNORECASE),
    "practice": re.compile(r"practice|method|process|engineering|devops|mlops", re.IGNORECASE),
    "expertise": re.compile(r"expertise|area|domain|concept|specialt|competenc|\bai\b|\bml\b|machine|data science",
                            re.IGNORECASE),
}
_NEW_CATEGORY = {"language": "Languages", "framework": "Frameworks & Libraries", "tool": "Tools & Platforms",
                 "practice": "Practices", "expertise": "Expertise"}
_GENERIC_CATEGORY_RE = re.compile(r"^\s*(?:skills?|other(?: skills)?|additional skills|technical skills)\s*$",
                                  re.IGNORECASE)
OTHER_SKILLS = "Other skills"

# Traits and attitudes: shown through the work, never listed as skills.
_TRAIT_RE = re.compile(
    r"\b(?:learner|learning agility|curio(?:us|sity)|passion(?:ate)?|motivat(?:ed|ion)|self[- ]starter|"
    r"team player|detail[- ]oriented|attention to detail|hard[- ]?working|eager|enthusias(?:m|tic)|mindset|"
    r"attitude|proactive|adaptab(?:le|ility)|flexib(?:le|ility)|growth mindset|ownership|go-getter|"
    r"self-driven|interpersonal|communication skills?|work ethic|initiative|positive attitude|energetic|"
    r"problem[- ]solver|collaborative|team[- ]?work)\b", re.IGNORECASE)


def is_trait(keyword: str, kind: str = "") -> bool:
    """A soft skill or trait ("Fast learner", "deep curiosity about AI"):
    something an example shows, not an item for the skills list."""
    return kind == "soft" or bool(_TRAIT_RE.search(keyword or ""))


def skill_type(term: str) -> Optional[str]:
    """language / framework / tool / practice / expertise, or None if unknown."""
    key = re.sub(r"\s+", " ", (term or "").strip().lower())
    for kind, terms in _TYPE_TERMS.items():
        if key in terms or key.rstrip("s") in terms:
            return kind
    return None


def jd_spelling(keyword: str, jd_text: str) -> str:
    """The keyword as the JD writes it ("CI" for "ci"), else as given."""
    m = re.search(r"(?<![\w.+#-])" + re.escape(keyword.strip()) + r"(?![\w+#-])", jd_text or "", re.IGNORECASE)
    return m.group(0) if m else keyword.strip()


def skill_category(skills: Dict[str, List[str]], term: str) -> str:
    """The category a confirmed skill belongs under: an existing one of its
    type, else a new one named for its type; an unknown term goes to an
    existing general category or "Other skills", never into a typed one."""
    kind = skill_type(term)
    if kind:
        for cat in skills:
            if _TYPE_CATEGORY_RE[kind].search(cat):
                return cat
        return _NEW_CATEGORY[kind]
    return next((c for c in skills if _GENERIC_CATEGORY_RE.match(c)), OTHER_SKILLS)

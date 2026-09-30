from typing import Dict, List

"""
Simple terminology registry for aliasing, acronyms, and phrase normalization.

This is intentionally lightweight: it provides in-memory maps and a
`normalize_phrase` helper used by scorer and matcher to canonicalize terms.
"""

__version__ = "0.1"

# Canonical alias map: canonical -> aliases.
# This is the single source of truth for term aliasing used by both
# EvidenceMatcher (whole-word substitution) and normalize_phrase (exact-phrase lookup).
ALIAS_MAP: Dict[str, List[str]] = {
    "machine learning": ["ml", "machine-learning"],
    "natural language processing": ["nlp"],
    "excel": ["ms excel", "microsoft excel"],
    "postgresql": ["postgres"],
    "kubernetes": ["k8s"],
    "aws": ["amazon web services"],
    "javascript": ["js"],
    "python": ["py"],
    "terraform": ["tf"],
    "artificial intelligence": ["ai"],
    "deep learning": ["dl"],
}

# Acronym map for expansion (kept for phrases that are acronym-only, e.g. "NLP" on its own).
ACRONYM_MAP: Dict[str, str] = {"nlp": "natural language processing", "ml": "machine learning"}

def flat_alias_to_canonical() -> Dict[str, str]:
    """Build a flat alias->canonical map (e.g. 'k8s' -> 'kubernetes') for
    whole-word regex substitution, derived from ALIAS_MAP so there is only
    one place to add/edit aliases."""
    flat: Dict[str, str] = {}
    for canonical, aliases in ALIAS_MAP.items():
        for alias in aliases:
            flat[alias] = canonical
    return flat

def normalize_phrase(phrase: str) -> str:
    """Normalize a phrase to its canonical lowercased form and expand common acronyms."""
    p = phrase.strip().lower()
    # Expand common acronyms
    if p in ACRONYM_MAP:
        p = ACRONYM_MAP[p]

    # Map known aliases to canonical term
    for canon, aliases in ALIAS_MAP.items():
        if p == canon or p in aliases:
            return canon

    # fallback: collapse multiple spaces and punctuation
    return " ".join(p.split())


# Common technical terms (lowercase) the offline JD analysis keeps wherever
# they appear, even sentence-initial ("Python and a web framework ...") or
# written in lowercase ("pytest", "dbt"). Names that are also ordinary words
# ("Go", "R", "Swift", "Rust", "Spark", "Excel", "Flask", "REST", "Spring",
# "Express", "Helm", "Lambda", "Hive", "Jest", "Rails", "Looker", "React",
# "Git") are left
# out: for them only the capitalisation rule applies, so "the rest of the
# team" doesn't yield REST.
TECH_TERMS = frozenset({
    # languages
    "python", "java", "javascript", "typescript", "scala", "kotlin", "c++", "c#", "golang", "ruby", "php",
    "sql", "nosql", "bash", "perl", "matlab", "sas", "haskell", "elixir", "clojure", "objective-c",
    # web / frameworks
    "angular", "vue", "vue.js", "next.js", "node.js", "django", "fastapi", "graphql", "grpc", "html", "css", "redux", "storybook", "webpack",
    # data / ml
    "pandas", "numpy", "scikit-learn", "sklearn", "pytorch", "tensorflow", "keras", "xgboost", "lightgbm",
    "catboost", "pyspark", "hadoop", "airflow", "dbt", "mlflow", "kubeflow", "databricks",
    "snowflake", "bigquery", "redshift", "tableau", "power bi", "jupyter", "langchain",
    "faiss", "llm", "llms", "nlp", "a/b testing", "etl", "elt",
    # stores / streaming
    "postgresql", "postgres", "mysql", "mongodb", "redis", "cassandra", "dynamodb", "elasticsearch",
    "kafka", "flink", "rabbitmq", "kinesis", "pubsub",
    # cloud / ops
    "aws", "azure", "gcp", "kubernetes", "k8s", "docker", "terraform", "ansible", "jenkins",
    "github actions", "gitlab ci", "ci/cd", "prometheus", "grafana", "datadog", "splunk", "linux", "serverless", "ec2", "s3",
    # testing / practice
    "pytest", "cypress", "selenium", "junit", "tdd", "microservices", "wcag",
    # product / compliance
    "jira", "figma", "hipaa", "gdpr", "sox", "pci dss", "okrs",
})

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
    # P8.17: acronyms outside tech, so "GAAP" and "Generally Accepted
    # Accounting Principles" are one keyword.
    "generally accepted accounting principles": ["gaap"],
    "lockout/tagout": ["loto", "lockout tagout", "lock out tag out"],
    "electronic health record": ["ehr"],
    "electronic medical record": ["emr"],
    "certified public accountant": ["cpa"],
    "project management professional": ["pmp"],
    "basic life support": ["bls"],
    "advanced cardiac life support": ["acls"],
    "pediatric advanced life support": ["pals"],
    "commercial driver's license": ["cdl", "commercial drivers license"],
    "customer relationship management": ["crm"],
    "enterprise resource planning": ["erp"],
    "key performance indicator": ["kpi"],
    "standard operating procedure": ["sop"],
    "service level agreement": ["sla"],
    "quality assurance": ["qa"],
    "national fire protection association": ["nfpa"],
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


# Terms outside tech the offline JD analysis keeps even in lowercase (P8.18):
# trades, care, warehouse, retail, finance, law, teaching. Ordinary words that
# are also skills elsewhere ("scheduling" is generic) stay out.
DOMAIN_TERMS = frozenset({
    # trades and warehouse
    "forklift", "pallet jack", "reach truck", "rf scanner", "conduit", "wiring", "blueprints", "plc", "plcs",
    "vfd", "vfds", "lockout/tagout", "nec", "nfpa 70e", "osha", "hazmat", "cdl", "inventory control", "wms",
    "bills of lading", "dot compliance", "preventive maintenance", "troubleshooting", "welding", "hvac",
    # care
    "telemetry", "wound care", "patient assessment", "care planning", "discharge teaching", "triage",
    "phlebotomy", "medication administration", "iv insertion", "vital signs", "hemodynamics", "ventilators",
    "infection control", "patient education", "charting", "epic", "cerner", "acls", "bls", "pals", "ccrn",
    # finance and business
    "month-end close", "reconciliations", "account reconciliations", "accruals", "journal entries",
    "financial statements", "financial reporting", "variance analysis", "budgeting", "forecasting", "audit",
    "sox", "asc 606", "revenue recognition", "accounts payable", "accounts receivable", "payroll", "netsuite",
    "quickbooks", "pivot tables", "vlookup", "p&l", "s&op", "six sigma", "lean six sigma", "kaizen",
    # sales and retail
    "pipeline management", "prospecting", "cold calling", "quota", "forecasting accuracy", "negotiation",
    "account management", "merchandising", "planograms", "loss prevention", "shrink", "cash handling",
    "pos", "visual merchandising", "customer service",
    # law
    "litigation", "depositions", "motion practice", "legal research", "legal writing", "e-discovery",
    "ediscovery", "contract drafting", "due diligence", "westlaw", "lexis", "relativity", "bar admission",
    # teaching and learning
    "lesson planning", "curriculum development", "classroom management", "differentiated instruction",
    "instructional design", "e-learning", "storyboards", "lms", "scorm", "addie", "assessment design",
})

# Benefits, perks and equal-opportunity words are never job keywords (P8.18:
# "Dental", "Vision", "ADA" and "PTO" were scored as skills).
BENEFIT_TERMS = frozenset({
    "dental", "vision", "medical", "pto", "paid time off", "401(k)", "401k", "403(b)", "403b", "health insurance",
    "life insurance", "tuition reimbursement", "parental leave", "equity", "stock options", "commission",
    "uncapped commission", "bonus", "wellness", "benefits", "perks", "eeo", "equal opportunity", "ada",
    "remote", "hybrid", "relocation", "visa sponsorship", "salary", "pay", "holidays",
})

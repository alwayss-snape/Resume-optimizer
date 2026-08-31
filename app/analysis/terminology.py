from typing import Dict, List

"""
Simple terminology registry for aliasing, acronyms, and phrase normalization.

This is intentionally lightweight: it provides in-memory maps and a
`normalize_phrase` helper used by scorer and matcher to canonicalize terms.
"""

__version__ = "0.1"

# Example alias map: canonical -> aliases
ALIAS_MAP: Dict[str, List[str]] = {
    "machine learning": ["ml", "machine-learning"],
    "natural language processing": ["nlp"],
}

# Acronym map for expansion
ACRONYM_MAP: Dict[str, str] = {"nlp": "natural language processing", "ml": "machine learning"}

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

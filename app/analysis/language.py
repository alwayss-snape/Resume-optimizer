"""Is this text in English? (P8.25)

Tailores reads and rewrites in English for now. A German or Spanish CV is
kept whole (P8.3) but can't be matched or rewritten well, so the user is
told so plainly instead of seeing a 0% score with no reason. A cheap check:
the share of very common function words of each language.
"""
import re
from typing import Optional

_COMMON = {
    "en": {"the", "and", "of", "to", "in", "for", "with", "on", "a", "an", "at", "by", "from", "as", "is", "are",
           "was", "our", "your", "you", "we", "will", "this", "that", "or"},
    "de": {"der", "die", "das", "und", "mit", "von", "für", "im", "in", "ein", "eine", "zu", "auf", "bei", "als",
           "sie", "wir", "ihr", "ihre", "oder", "des", "den", "dem", "kenntnisse"},
    "es": {"el", "la", "los", "las", "y", "de", "del", "en", "con", "para", "por", "un", "una", "que", "al", "se",
           "su", "sus", "o", "requisitos"},
    "fr": {"le", "la", "les", "et", "de", "des", "du", "en", "avec", "pour", "par", "un", "une", "que", "au", "aux",
           "sur", "vous", "nous", "ou"},
}


def other_language(text: str) -> Optional[str]:
    """"German" / "Spanish" / "French" when the text reads as that rather
    than English; None for English or too little text to tell."""
    words = [w.lower() for w in re.findall(r"[^\W\d_]+", text or "")]
    if len(words) < 25:
        return None
    share = {lang: sum(w in vocab for w in words) / len(words) for lang, vocab in _COMMON.items()}
    best = max(share, key=share.get)
    if best != "en" and share[best] > 2 * share["en"] and share[best] >= 0.04:
        return {"de": "German", "es": "Spanish", "fr": "French"}[best]
    return None


def english_only_note(what: str, language: str) -> str:
    return (f"Tailores works in English for now, and your {what} looks like it's in {language}. Nothing on your "
            "resume is lost, but the match and the rewrites need English; more languages are planned.")

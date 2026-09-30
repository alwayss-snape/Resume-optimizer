"""Local profile of facts the user has confirmed (P3.2).

When the user answers a gap question ("I have used Kafka", "where and how"),
that answer is saved here and offered again on the next JD that asks about
the same keyword, so the same question isn't answered twice. It is only a
pre-fill: the user still sees the question and must keep it ticked, so
nothing is ever added without their confirmation for that JD.

Stored as JSON under data/profile/ (gitignored): the file itself stays on
this machine. A saved answer the user keeps for a JD is polished by the
LLM like any other gap answer.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, Field, ValidationError

from app.config.settings import settings

logger = logging.getLogger(__name__)


class ConfirmedFact(BaseModel):
    keyword: str                      # as the JD spelled it, e.g. "Kafka"
    answer: str = ""                  # the user's own words, if they gave any
    requirement: str = ""             # the JD line it was asked for
    confirmed_at: str = ""            # ISO timestamp of the last confirmation


class Profile(BaseModel):
    version: int = 1
    facts: Dict[str, ConfirmedFact] = Field(default_factory=dict)  # lowercased keyword -> fact


class ProfileStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or settings.profile_path

    def load(self) -> Profile:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return Profile.model_validate(data)
        except FileNotFoundError:
            return Profile()
        except (json.JSONDecodeError, ValidationError, UnicodeDecodeError):
            # A damaged file must not break tailoring; start fresh (the old
            # file is kept next to it for the user to inspect).
            try:
                os.replace(self.path, self.path + ".corrupt")
            except OSError:
                pass
            return Profile()
        except OSError as e:
            # Unreadable (permissions, a directory, ...): not corrupt, so
            # leave it alone and carry on without saved answers.
            logger.warning(f"Could not read the saved-answers profile at {self.path}: {e}")
            return Profile()

    def save(self, profile: Profile) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)  # atomic: a crash never leaves half a file

    def record(self, answers: Iterable, questions: Iterable) -> List[str]:
        """Save the confirmed keywords (and answer text) from gap answers.
        Returns the keywords saved."""
        by_id = {q.id: q for q in questions}
        profile = self.load()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        saved = []
        for ans in answers:
            get = ans.get if isinstance(ans, dict) else (lambda k, d=None, a=ans: getattr(a, k, d))
            question = by_id.get(get("question_id", ""))
            answer = (get("answer", "") or "").strip()
            # Answers already saved under other keywords: a pre-filled answer
            # that the user left as is belongs to those keywords only, not to
            # every keyword ticked next to it.
            existing = {f.answer for f in profile.facts.values() if f.answer}
            for keyword in get("confirmed_keywords", []) or []:
                if not keyword.strip():
                    continue
                key = keyword.strip().lower()
                previous = profile.facts.get(key)
                own = previous.answer if previous else ""
                reused = answer in existing and answer != own
                profile.facts[key] = ConfirmedFact(
                    keyword=keyword.strip(),
                    # A new answer replaces the old one; no answer (or someone
                    # else's pre-filled answer) keeps this keyword's own.
                    answer=own if (not answer or reused) else answer,
                    requirement=question.requirement if question else (previous.requirement if previous else ""),
                    confirmed_at=now,
                )
                saved.append(keyword.strip())
        if saved:
            self.save(profile)
        return saved

    def known(self, keywords: Iterable[str]) -> Dict[str, ConfirmedFact]:
        """Saved facts for these keywords (case-insensitive), keyed as given."""
        facts = self.load().facts
        return {k: facts[k.lower()] for k in keywords if k.lower() in facts}

    def forget(self, keyword: Optional[str] = None) -> int:
        """Forget one keyword, or everything when keyword is None. Returns how many were removed."""
        profile = self.load()
        if keyword is None:
            removed = len(profile.facts)
            profile.facts = {}
        else:
            removed = 1 if profile.facts.pop(keyword.lower(), None) else 0
        if removed:
            self.save(profile)
        return removed

"""Semantic (embedding-based) matching layer.

Design constraints (see ARCHITECTURE.md / PR discussion):
- This layer NEVER runs before the deterministic EvidenceMatcher, and NEVER
  overrides or modifies a match that already has status EXPLICIT, SUPPORTED,
  or PARTIAL. It only considers requirements still MISSING after the
  deterministic pass.
- A positive result is always a new, clearly distinct status
  (SEMANTIC_PARTIAL), always carries the matched evidence id and the raw
  similarity score in `confidence`, and always explains itself in plain text
  referencing that evidence — mirroring the transparency contract
  EvidenceMatcher already uses for EXPLICIT/SUPPORTED/PARTIAL.
- This module must never crash the pipeline if the optional
  `sentence-transformers` dependency is missing, unavailable, or disabled via
  settings. In that case it is a no-op: the deterministic matches pass
  through unchanged. This mirrors the "never fail the tailoring flow" pattern
  used elsewhere in this codebase (see app/services/tailor.py QA/PDF steps).
"""

from typing import Callable, List, Optional, Sequence

from app.domain.evidence import Evidence
from app.domain.job import Requirement
from app.domain.report import Match

# Type alias for an injectable embedding backend: given a list of strings,
# return a list of embedding vectors (each a sequence of floats). This lets
# tests inject a cheap fake embedder instead of loading a real ML model, and
# lets callers swap models without touching this file.
Embedder = Callable[[Sequence[str]], List[Sequence[float]]]


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticMatcher:
    """Adds SEMANTIC_PARTIAL matches for requirements the deterministic
    matcher left MISSING, using sentence embedding similarity.

    Usage:
        matcher = SemanticMatcher()  # lazy-loads sentence-transformers on first match()
        matches = matcher.match(requirements, evidence_list, existing_matches)

    For tests, inject a fake embedder to avoid loading a real model:
        matcher = SemanticMatcher(embedder=my_fake_embedder)
    """

    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        model_name: Optional[str] = None,
        threshold: Optional[float] = None,
        enabled: Optional[bool] = None,
    ):
        # Deferred import of settings to avoid a hard dependency at module
        # import time for callers who construct this with an explicit
        # embedder/threshold (e.g. tests).
        if model_name is None or threshold is None or enabled is None:
            from app.config.settings import settings
            model_name = model_name if model_name is not None else settings.semantic_match_model
            threshold = threshold if threshold is not None else settings.semantic_match_threshold
            enabled = enabled if enabled is not None else settings.semantic_match_enabled

        self._explicit_embedder = embedder
        self._model_name = model_name
        self._threshold = threshold
        self._enabled = enabled
        self._model = None  # lazy-loaded SentenceTransformer instance
        self._unavailable = False  # set True if the real model failed to load once

    def _get_embedder(self) -> Optional[Embedder]:
        if self._explicit_embedder is not None:
            return self._explicit_embedder
        if self._unavailable:
            return None
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
            except Exception:
                # Missing dependency, no network for first-time model download,
                # or any other load failure: semantic matching is skipped, not fatal.
                self._unavailable = True
                return None

        def _encode(texts: Sequence[str]) -> List[Sequence[float]]:
            return self._model.encode(list(texts))

        return _encode

    def match(
        self,
        requirements: List[Requirement],
        evidence_list: List[Evidence],
        existing_matches: List[Match],
    ) -> List[Match]:
        """Returns a new match list: every non-MISSING match from
        `existing_matches` is passed through unchanged; MISSING matches are
        replaced with a SEMANTIC_PARTIAL match if a sufficiently similar
        evidence item is found, otherwise left as MISSING."""
        if not self._enabled:
            return list(existing_matches)

        existing_by_id = {m.requirement_id: m for m in existing_matches}
        missing_requirements = [
            req for req in requirements
            if existing_by_id.get(req.id) is not None
            and existing_by_id[req.id].status == "MISSING"
        ]

        if not missing_requirements:
            return list(existing_matches)

        usable_evidence = [ev for ev in evidence_list if ev.text.strip()]
        if not usable_evidence:
            return list(existing_matches)

        embedder = self._get_embedder()
        if embedder is None:
            return list(existing_matches)

        req_texts = [req.text for req in missing_requirements]
        evidence_texts = [ev.text for ev in usable_evidence]

        try:
            req_embeddings = embedder(req_texts)
            evidence_embeddings = embedder(evidence_texts)
        except Exception:
            # A runtime embedding failure (e.g. OOM) must not take down the
            # rest of the pipeline; fall back to the deterministic result.
            return list(existing_matches)

        results: List[Match] = list(existing_matches)
        results_by_id = {m.requirement_id: i for i, m in enumerate(results)}

        for req, req_emb in zip(missing_requirements, req_embeddings):
            best_score = -1.0
            best_evidence: Optional[Evidence] = None
            for ev, ev_emb in zip(usable_evidence, evidence_embeddings):
                score = _cosine_similarity(req_emb, ev_emb)
                if score > best_score:
                    best_score = score
                    best_evidence = ev

            if best_evidence is not None and best_score >= self._threshold:
                idx = results_by_id[req.id]
                results[idx] = Match(
                    requirement_id=req.id,
                    requirement_text=req.text,
                    status="SEMANTIC_PARTIAL",
                    evidence_ids=[best_evidence.id],
                    explanation=(
                        f"Semantically similar to resume evidence {best_evidence.id} "
                        f"(similarity {best_score:.2f}): \"{best_evidence.text[:100]}\""
                    ),
                    confidence=round(best_score, 2),
                )
            # else: leave the existing MISSING match untouched.

        return results

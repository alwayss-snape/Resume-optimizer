# Architecture Document — Local Resume Tailor

## Architectural Core Directive

> **The LLM edits content; deterministic code owns document structure, formatting, validation, and file generation.**

## Pipeline Flow

```text
Input Resume (.docx / .pdf) + JD Text
  │
  ├──► Ingestion (DOCX Parser / PDF OCR) -> Raw Document & DocumentMap
  ├──► Resume Normalizer -> Canonical Resume Model + Evidence Ledger
  ├──► JD Analyzer -> Job Description Requirements Model
  ├──► Evidence Matcher (Deterministic: Exact phrase, Alias/synonym, Token overlap) -> Match Report
  ├──► Semantic Matcher (Local embedding model; only requirements left MISSING above) -> Match Report (adds SEMANTIC_PARTIAL)
  ├──► Tailoring Planner -> Tailoring Plan (Grounded in Evidence)
  ├──► LLM Rewrite Engine -> Rewritten Bullet / Summary / Skills Proposals
  ├──► Factual & Structural Validator Gate -> Approved / Rejected Items
  ├──► Canonical Resume Document (JSON + revision history)
  ├──► Rendering Engine (Preserve DOCX / ATS DOCX / ATS HTML-CSS) -> DOCX + HTML
  ├──► PDF Converter (Headless LibreOffice) -> Tailored PDF
  └──► Output QA & Audit Log -> Report & Change Log
```

### Semantic Matching Design

The Evidence Matcher never uses an LLM or embeddings — it is a deterministic pass over exact phrase containment, alias/synonym lookup (`app/analysis/terminology.py`), and token-set overlap. This layer is fully auditable: every match traces to a specific rule and a specific evidence id.

The Semantic Matcher (`app/analysis/semantic_matcher.py`) is a separate, secondary layer added after the deterministic pass:

- It only runs on requirements the deterministic matcher left `MISSING` — it never re-evaluates or overrides an `EXPLICIT`, `SUPPORTED`, or `PARTIAL` match.
- A positive result is always a distinct status (`SEMANTIC_PARTIAL`), always carries the matched evidence id, the raw similarity score, and an explanation referencing that evidence.
- It is excluded from the headline `alignment_score` — semantic coverage is surfaced separately (`ScoreComponents.semantic_coverage`) so an inferred paraphrase match is never silently counted as hard evidence.
- It is optional and fails soft: if the embedding model or its dependency is unavailable, disabled, or fails to load, the deterministic matches pass through unchanged rather than blocking the pipeline. See `SEMANTIC_MATCH_ENABLED`/`SEMANTIC_MATCH_THRESHOLD`/`SEMANTIC_MATCH_MODEL` in configuration.

## Security & Privacy Constraints

- **Default: local-only.** Ollama (`qwen3:4b` default) for rewriting, and a local sentence-embedding model
  (`all-MiniLM-L6-v2` default) for semantic matching. Zero external API dependencies in this mode.
- **Optional: Groq provider.** `app/llm/client.py` also supports routing generation through
  [Groq](https://console.groq.com)'s free cloud inference API (`LLM_PROVIDER=groq`, OpenAI-compatible
  `chat/completions` endpoint) when a stronger model than the local default is needed. This is opt-in only —
  the default remains Ollama — but when enabled, prompt content (which includes resume and JD text) is sent to
  Groq's servers, and Groq's own data-handling terms apply. Anyone deploying this for others' resumes should be
  aware of that before switching providers.
- No network logging of sensitive personal candidate data by this application, in either mode.

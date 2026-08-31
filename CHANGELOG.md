# Changelog — Local Resume Tailor

## [Unreleased] - 2026-08-31

### Changed
- Project baseline restoration and V2 planning started. Test count in this
	environment progressed from 36 -> 59 passing over this session.
- Consolidated alias/synonym maps: `app/analysis/matcher.py` previously
	duplicated its own `ALIASES` dict separately from
	`app/analysis/terminology.py::ALIAS_MAP`. Now `terminology.py` is the
	single source of truth; `matcher.py` derives its flat alias map from it.
- Removed unused `app/analysis/evidence_index.py` scaffolding (never wired
	into the matcher; no consumer or test coverage).

### Added
- **Per-run LLM token-usage tracking:** `LLMClient` now records every `generate()` call (provider, model, prompt/completion tokens, duration, success/failure) to `self.usage_log`; `get_usage_summary()` aggregates it. `TailorService.tailor_resume()` saves this as `data/runs/<run_id>/llm_usage.json` and a short summary in `changes.md`, so real per-run token consumption is measurable instead of estimated — the basis for deciding whether a single Groq model has enough free-tier headroom or a fast/strong split is worth the added complexity.
- **Groq provider support (opt-in, off by default):** `app/llm/client.py` can now route generation through Groq's free cloud inference API instead of local Ollama, selected via `LLM_PROVIDER=groq` (`GROQ_API_KEY`/`GROQ_MODEL` in `.env`). Implemented as a second provider branch behind the same `generate`/`generate_json`/`is_available` interface, using `httpx` against Groq's OpenAI-compatible `chat/completions` endpoint — no other call site changed. Ollama remains the default; enabling Groq sends resume/JD text off-device, documented in `ARCHITECTURE.md` and `BUILD.md`. New `httpx` dependency (`pyproject.toml`); new Groq-path tests in `tests/unit/test_llm_client.py`.
- Real-time `changes.md` progress logging in `app/services/tailor.py`.
- `ChangeProposal` schema and UI review flow: proposals can be generated, reviewed, edited, and applied from the Streamlit UI.
- Terminology registry, now the single source of truth for term aliasing: `app/analysis/terminology.py`.
- Deterministic scorer components and breakdown: `app/analysis/scoring.py`.
- Preview fallback: prefer `st.pdf`, fall back to local HTTP PDF preview or PNG raster via PyMuPDF in `app/ui.py`.
- **Semantic Matching Layer:** `app/analysis/semantic_matcher.py` — a local
	sentence-embedding model (`all-MiniLM-L6-v2` default) that runs only on
	requirements the deterministic `EvidenceMatcher` leaves `MISSING`, never
	overrides a deterministic match, and always surfaces the matched
	evidence + similarity score. New `SEMANTIC_PARTIAL` match status
	(`app/domain/report.py`). Excluded from the headline `alignment_score`;
	surfaced separately as `ScoreComponents.semantic_coverage`
	(`app/analysis/scoring.py`) so an inferred paraphrase match is never
	silently counted as hard evidence. Fails soft if the optional
	`sentence-transformers` dependency is missing/disabled/fails to load.
	Configurable via `SEMANTIC_MATCH_ENABLED` / `SEMANTIC_MATCH_THRESHOLD`
	(default `0.58`) / `SEMANTIC_MATCH_MODEL` (`app/config/settings.py`).
	Wired into all three `TailorService` entry points
	(`analyze_only`, `generate_proposals`, `tailor_resume`) as a single
	reused instance so the model loads once, not per call.

### Fixed
- **PDF word-wrap truncation:** `PdfParser` (`app/ingestion/pdf.py`) treated
	every visually-wrapped line of a bullet/paragraph as its own separate
	block, truncating long bullets into disconnected fragments and starving
	both matchers of complete sentences. Fixed with a conservative merge
	rule (`_merge_wrapped_lines`): a line is joined onto the previous one
	only when it starts with a lowercase letter, since genuine mid-sentence
	wrap virtually never starts a new visual line with a capital letter,
	while headings/names/bullets do. Verified against both a real-world PDF
	(previously-truncated MLOps bullet now comes through complete) and the
	existing `sample.pdf` fixture (candidate name / section headings
	continue to extract as separate, correct blocks).
- **JD heading leakage:** `JDAnalyzer.HEADING_RE` (`app/analysis/jd_analyzer.py`)
	only matched a small set of exact heading phrases, so common real-world
	variants like "Minimum Qualifications" or "Technical Skills" fell
	through and were extracted as nonsensical standalone requirements.
	Broadened the regex to accept a common qualifier prefix (Minimum/
	Preferred/Required/Basic/Desired/Additional/Other/Key/Core/Technical/
	Essential/Primary/General) before Responsibilities/Requirements/
	Qualifications/Skills. Also fixed the trailing-whitespace character
	class, which was matching literal `\`+`s` characters instead of
	whitespace due to an over-escaped raw string (`[:\\s]*$` -> `[:\s]*$`).
- **Slash-alternatives treated as conjunctive:** `EvidenceMatcher`
	(`app/analysis/matcher.py`) treated a requirement like "AWS/GCP" as
	requiring *both* AWS and GCP rather than *either*, so a resume with only
	AWS scored as 50% coverage of a compound token set instead of a full
	match. Added `_extract_requirement_units`, which treats a
	slash-separated group as one unit satisfied by any one of its
	alternatives, while other requirement tokens are still matched as
	before.
- **Scoring required-bucket mismatch:** `AlignmentScorer.calculate_components`
	(`app/analysis/scoring.py`) only bucketed a requirement as "required" when
	`criticality == "critical"`, but `Requirement.criticality` defaults to
	`"required"` (`app/domain/job.py`) — so most ordinary requirements were
	silently scored as `keyword_coverage` instead of `required_coverage`.
	Fixed by including `"required"` in the bucket check. This intentionally
	changes existing score outputs.
- **Planner didn't distinguish inferred matches in rewrite rationale:**
	`TailoringPlanner.create_plan` (`app/analysis/tailor_planner.py`) picked
	the first matched requirement for a bullet's rewrite rationale regardless
	of match status, so a `SEMANTIC_PARTIAL` (inferred) match could be
	presented with the same wording as an exact match. Now prefers a
	deterministic match for the rationale when one exists, and labels the
	rationale "inferred via semantic similarity, not an exact match" when
	only a semantic match supports it. The underlying action decision
	(bullets with a semantic-only match still get REWRITE) is unchanged —
	this only makes the reasoning transparent.

## [0.2.0] - 2026-08-30

### In Progress
- **Redesign Phase 1 — Canonical Resume Document:** Added `ResumeDocument`, a versioned JSON source of truth holding résumé content, presentation preferences, import metadata, and an auditable revision history.
- Added unit coverage for JSON snapshots and import revision provenance.
- Independent source review completed. The model contract is sound; service/UI adoption is intentionally scheduled for subsequent phases.

## [0.1.0] - 2026-08-29

### Added
- **Phase 0 — Repository & Environment:** Pyproject, virtual environment setup, configuration loading.
- **Phase 1 — Local LLM Harness:** `LLMClient` wrapping Ollama API with schema enforcement and retries (`qwen3:4b` default).
- **Phase 2 — DOCX Ingestion:** `DocxParser` extracting raw blocks, headings, bullets, tables, and `DocumentMap`.
- **Phase 3 — PDF Ingestion:** `PdfParser` using PyMuPDF and `OCREngine` fallback path.
- **Phase 4 — Resume Normalization:** Canonical `Resume` model and `Evidence` ledger generator.
- **Phase 5 — JD Analysis:** `JDAnalyzer` extracting required/preferred skills, responsibilities, and qualifications.
- **Phase 6 — Matching Engine:** 3-Layer hybrid matcher (`EXPLICIT`, `SUPPORTED`, `PARTIAL`, `MISSING`, `UNCERTAIN`) and weighted scoring.
- **Phase 7 — Tailoring Planner:** Grounded `TailoringPlanner` mapping rewrites strictly to source evidence IDs.
- **Phase 8 — Controlled Rewriter:** `LLMRewriter` with evidence constraints and deterministic fallback.
- **Phase 9 — Validation Gate:** Multi-layer factual validator, numeric mutation checker, structural validator, and safety guard.
- **Phase 10 — DOCX Renderer:** `DocxPatcher` for in-place run patching and `TemplateRenderer` for ATS templates.
- **Phase 11 — PDF Renderer & Output QA:** `PdfConverter` (LibreOffice headless) and `OutputQAValidator`.
- **Phase 12 — CLI Interface & Service:** `TailorService` orchestrator, `RunManager`, and CLI `analyze` / `tailor` subcommands.
- **Phase 13 — Streamlit Web UI:** Interactive dashboard for resume optimization and report viewing.
- **Phase 14 — End-to-End Hardening:** Integration test suite covering safety, layout preservation, and multi-format rendering.

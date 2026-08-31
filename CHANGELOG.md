# Changelog — Local Resume Tailor

## [Unreleased] - 2026-08-31

### Changed
- Project baseline restoration and V2 planning started. Current test
	count in this environment: 29 passing.

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

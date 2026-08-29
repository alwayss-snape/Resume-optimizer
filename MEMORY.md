# Project Memory — Local Resume Tailor

## Current Phase

Phase 14 — End-to-End Hardening (V1 COMPLETE)

## Overall Status

Completed & Hardened

## Last Updated

2026-08-29

## What Has Been Completed

- Phase 0: Created `resume-tailor/` directory structure, virtualenv `.venv`, dependencies, `pyproject.toml`, `.env`, `BUILD.md`, `ARCHITECTURE.md`, `README.md`.
- Phase 1: Local LLM Harness (`LLMClient`, Pydantic schemas, prompt templates, unit tests, benchmark script).
- Phase 2: DOCX Ingestion & Document Map (`DocumentMap`, `DocxParser`, sample fixture generator, unit tests).
- Phase 3: PDF Ingestion & OCR Path (`OCREngine`, `PdfParser`, sample fixture generator, unit tests).
- Phase 4: Resume Normalization & Evidence Ledger (`Resume`, `Evidence`, `ResumeNormalizer`, unit tests).
- Phase 5: JD Analysis (`Requirement`, `JobDescription`, `JDAnalyzer`, unit tests).
- Phase 6: Matching Engine (`Match`, `TailoringReport`, `AlignmentScorer`, `EvidenceMatcher`, unit tests).
- Phase 7: Tailoring Planner (`TailoringAction`, `TailoringPlan`, `TailoringPlanner`, unit tests).
- Phase 8: Controlled Rewriting Engine (`RewriteProposal`, `LLMRewriter`, unit tests).
- Phase 9: Multi-Layer Validation Gate (`FactualValidator`, `StructuralValidator`, `SafetyGuard`, unit tests).
- Phase 10: DOCX Patch Engine & Renderer (`DocxPatcher`, `TemplateRenderer`, unit tests).
- Phase 11: PDF Renderer & Output QA (`PdfConverter`, `OutputQAValidator`, unit tests).
- Phase 12: CLI Interface & Service Layer (`RunManager`, `TailorService`, `app/cli.py`, unit tests).
- Phase 13: Streamlit Web UI (`app/ui.py`, unit tests).
- Phase 14: End-to-End Hardening (`tests/integration/test_end_to_end.py`, `CHANGELOG.md`).
- Resolved PDF heading operator precedence edge case in `PdfParser` and verified candidate name extraction across all formats.
- Added explicit `sys.path` project root resolution in `app/ui.py` and `app/cli.py` to prevent `ModuleNotFoundError: No module named 'app'` when running Streamlit from subdirectories or arbitrary working directories.
- Verified 100% passing test suite across all 29 unit and integration tests.

## What Is Currently Being Worked On

Project V1 implementation is complete, fully tested, and hardened.

## Next Immediate Task

V1 is complete. Application is ready for local production use via CLI or Streamlit UI.

## Completed Phases

- Phase 0 — Repository and Environment
- Phase 1 — Local LLM Harness
- Phase 2 — DOCX Ingestion
- Phase 3 — PDF Ingestion
- Phase 4 — Resume Normalization
- Phase 5 — JD Analysis
- Phase 6 — Matching Engine
- Phase 7 — Tailoring Planner
- Phase 8 — Controlled Rewriting
- Phase 9 — Validation Gate
- Phase 10 — DOCX Renderer
- Phase 11 — PDF Renderer
- Phase 12 — CLI Interface
- Phase 13 — Streamlit UI
- Phase 14 — End-to-End Hardening

## Remaining Phases

None — V1 Complete

## Files Created/Modified

- `pyproject.toml`, `.gitignore`, `.env.example`, `.env`, `BUILD.md`, `ARCHITECTURE.md`, `README.md`, `MEMORY.md`, `CHANGELOG.md`
- `app/config/settings.py`, `app/llm/client.py`, `app/llm/schemas.py`, `app/llm/prompts/*`
- `app/domain/*` (`resume.py`, `job.py`, `evidence.py`, `tailoring.py`, `report.py`)
- `app/ingestion/*` (`docx.py`, `pdf.py`, `ocr.py`)
- `app/analysis/*` (`resume_normalizer.py`, `jd_analyzer.py`, `matcher.py`, `scoring.py`, `tailor_planner.py`, `rewriter.py`)
- `app/validation/*` (`factual.py`, `structural.py`, `output.py`, `safety.py`)
- `app/rendering/*` (`document_map.py`, `docx_patcher.py`, `template_renderer.py`, `pdf_converter.py`)
- `app/services/*` (`tailor.py`, `run_manager.py`)
- `app/cli.py`, `app/ui.py`
- `scripts/*` (`benchmark_model.py`, `create_sample_docx.py`, `create_sample_pdf.py`)
- `tests/*` (29 unit & integration test cases)

## Current Architecture Decisions

- Local-first execution via Ollama (`qwen3:4b` default).
- Zero external API dependencies, strict evidence ledger prevents hallucination.
- Dual output layout modes (`PRESERVE` in-place run patching vs `ATS_DEFAULT` template rendering).
- Dynamic `sys.path` project root injection at entrypoints (`app/ui.py`, `app/cli.py`).

## Dependencies Added

- `pydantic`, `pydantic-settings`, `python-docx`, `pymupdf`, `ollama`, `streamlit`, `python-dotenv`, `pytest`

## Tests

### Passing

- All 29 unit & integration test cases pass cleanly.

### Failing

- None

### Last Test Command

```bash
pytest -q
```

## Known Issues

- `libreoffice` binary not currently installed in system PATH; PDF conversion will fallback or require LibreOffice installation.

## Decisions / Rationale

### 2026-08-29 — V1 Release Checkpoint Passed

All 15 phases (0-14) completed, validated, and verified with 100% test pass rate.

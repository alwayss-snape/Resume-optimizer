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
  ├──► Evidence Matcher (Hybrid: Exact, Alias, LLM Semantic) -> Match Report
  ├──► Tailoring Planner -> Tailoring Plan (Grounded in Evidence)
  ├──► LLM Rewrite Engine -> Rewritten Bullet / Summary / Skills Proposals
  ├──► Factual & Structural Validator Gate -> Approved / Rejected Items
  ├──► Rendering Engine (DOCX Patch Engine / ATS Template Renderer) -> Tailored DOCX
  ├──► PDF Converter (Headless LibreOffice) -> Tailored PDF
  └──► Output QA & Audit Log -> Report & Change Log
```

## Security & Privacy Constraints

- All models run locally via Ollama (`qwen3:4b` default).
- Zero external API dependencies.
- No network logging of sensitive personal candidate data.

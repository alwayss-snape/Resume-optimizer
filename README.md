# Local Resume Tailor

Local-first, privacy-focused application for tailoring resumes to job descriptions using local LLMs (Ollama + Qwen3).

## Key Features

- **Strict Factual Accuracy:** Never fabricates skills, dates, employers, metrics, or certifications.
- **Evidence Ledger:** All rewrites reference verifiable source evidence.
- **Layout Preservation:** Patches existing `.docx` elements preserving formatting, fonts, and styles.
- **Hybrid Matching Engine:** Exact, alias, and semantic evidence matching.
- **CLI & Web UI:** Includes both a command-line interface and a Streamlit dashboard.

## Quick Start

See [BUILD.md](BUILD.md) for installation and environment setup.

## Development

- Create and activate a virtualenv, then install dependencies from `pyproject.toml`.
- Use `pytest` to run tests.

Auto-commit helper

If you want an automated local helper to commit & push changes periodically (for example during long-running development), run:

```
./scripts/autocommit.sh 300 "Auto-commit: periodic checkpoint"
```

This script is intended to be run manually by a developer and will not be started by the application.

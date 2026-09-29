# Local Resume Tailor

Local-first, privacy-focused application for tailoring resumes to job descriptions using local LLMs (Ollama + Qwen3) and a local sentence-embedding model for semantic matching. Optionally, generation can be routed through [Groq](https://console.groq.com) (free cloud inference) instead of Ollama when a stronger model is needed — see `BUILD.md`; this is opt-in and sends resume/JD text off-device.

## Key Features

- **Strict Factual Accuracy:** Never fabricates skills, dates, employers, metrics, or certifications.
- **Evidence Ledger:** All rewrites reference verifiable source evidence.
- **Layout Preservation:** Patches existing `.docx` elements preserving formatting, fonts, and styles.
- **Hybrid Matching Engine:** Exact, alias, and local embedding-based semantic matching. The semantic layer only considers requirements the deterministic layer leaves unmatched, is clearly labeled as an inferred (not exact) match wherever shown, and never overrides a deterministic match.
- **CLI & Web UI:** Includes both a command-line interface and a Streamlit dashboard.

## Quick Start

See [BUILD.md](BUILD.md) for installation and environment setup.

## Documentation

- [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md): start here. What the tool does, current status, open issues, next work.
- [docs/KNOWLEDGE_GRAPH.md](docs/KNOWLEDGE_GRAPH.md): where everything lives (auto-generated on every commit).
- [docs/CHANGE_LOG.md](docs/CHANGE_LOG.md): timestamped log of major changes (auto-appended on every major commit).
- [ARCHITECTURE.md](ARCHITECTURE.md): design principles and privacy constraints.

## Development

- Create and activate a virtualenv, then install dependencies from `pyproject.toml`.
- Use `pytest` to run tests.

Auto-commit helper

If you want an automated local helper to commit & push changes periodically (for example during long-running development), run:

```
./scripts/autocommit.sh 300 "Auto-commit: periodic checkpoint"
```

This script is intended to be run manually by a developer and will not be started by the application.

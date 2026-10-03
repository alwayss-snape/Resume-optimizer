# Tailores

Tailores tailors a resume to a job description: it reads the resume, scores it against the job's keywords, drafts fact-checked rewrites, and builds an ATS-friendly DOCX and PDF. **Where your data goes:** the text of the resume and the job description is sent to the configured AI provider to draft rewrites and read the job description. With `LLM_PROVIDER=groq` (the default setup) that is Groq's cloud service; with `LLM_PROVIDER=ollama` it stays on the machine running the server. Semantic matching uses a local embedding model. In the web app, uploads and results live only for the visit and are deleted when it ends (see `API_SESSION_TTL_MINUTES`).

## Key Features

- **Strict Factual Accuracy:** Never fabricates skills, dates, employers, metrics, or certifications.
- **Evidence Ledger:** All rewrites reference verifiable source evidence.
- **Layout Preservation:** Patches existing `.docx` elements preserving formatting, fonts, and styles.
- **Hybrid Matching Engine:** Exact, alias, and local embedding-based semantic matching. The semantic layer only considers requirements the deterministic layer leaves unmatched, is clearly labeled as an inferred (not exact) match wherever shown, and never overrides a deterministic match.
- **Web app & CLI:** A React web app (`web/`) on a FastAPI backend (`app/api/`): upload, check what was read,
  review every rewrite with a live match score, then download DOCX/PDF. Also a command-line interface.

## Quick Start

See [BUILD.md](BUILD.md) for installation and environment setup.

## Documentation

- [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md): start here. What the tool does, current status, open issues, next work.
- [docs/ACTION_ITEMS.md](docs/ACTION_ITEMS.md): improvement roadmap with live status per item.
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

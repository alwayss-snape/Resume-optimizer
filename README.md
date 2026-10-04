# Tailores

Tailores tailors a resume to a job description: it reads the resume, scores it against the job's keywords, drafts fact-checked rewrites, and builds an ATS-friendly DOCX and PDF. **Where your data goes:** the text of the resume and the job description is sent to the configured AI provider to draft rewrites and read the job description. With `LLM_PROVIDER=groq` (the default setup) that is Groq's cloud service; with `LLM_PROVIDER=ollama` it stays on the machine running the server. Semantic matching uses a local embedding model. In the web app, uploads and results live only for the visit and are deleted when it ends (see `API_SESSION_TTL_MINUTES`).

## Key Features

- **Strict Factual Accuracy:** Never fabricates skills, dates, employers, metrics, or certifications.
- **Evidence Ledger:** All rewrites reference verifiable source evidence.
- **Any resume file:** `.docx`, `.pdf`, `.doc`, `.odt`, `.rtf`, `.txt` or pasted text. A damaged, empty,
  password-protected or scanned file gets its own plain message instead of an error.
- **ATS template or your own layout:** a clean A4 ATS template fitted to 1 or 2 pages by experience (the default), or
  your original `.docx` patched in place, keeping its formatting (an advanced option).
- **Arrange and edit:** after the AI changes, reorder sections, jobs and bullets, hide sections, reword a bullet and
  bring back what page-fit trimmed; re-rendered with no AI call, and checked so no line is lost.
- **A fair, explained score:** works outside tech (alternatives, acronyms, degree levels, licences and shifts as a
  separate checklist), resists keyword stuffing, and says why a low match is low.
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

- Create and activate a virtualenv, then install dependencies from `pyproject.toml` (see [BUILD.md](BUILD.md)).
- Backend tests: `.venv_py311/bin/python -m pytest -q` (~4 min; needs `sentence-transformers`).
  The offline persona and eval cases: `pytest -q -m eval` (needs LibreOffice).
- Front-end tests: `cd web && npm test`. Build the app with `npm run build`; uvicorn then serves it.
- Browser walkthrough (1440 / 390 px, light and dark, in Chrome, no AI quota used):
  `PYTHONPATH=. uvicorn scripts.walkthrough_server:app --port 8010`, then
  `cd web && OUT=/tmp/shots node ../scripts/walkthrough.cjs`.

Auto-commit helper

If you want an automated local helper to commit & push changes periodically (for example during long-running development), run:

```
./scripts/autocommit.sh 300 "Auto-commit: periodic checkpoint"
```

This script is intended to be run manually by a developer and will not be started by the application.

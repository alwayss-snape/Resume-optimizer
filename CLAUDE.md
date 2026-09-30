# CLAUDE.md

## Orientation

- Read `docs/PROJECT_OVERVIEW.md` first (what the tool does, current status, open issues, next work), then use
  `docs/KNOWLEDGE_GRAPH.md` to find where things live instead of re-exploring the tree.
- `docs/CHANGE_LOG.md` is the timestamped history of major changes, with the reasoning behind them.
- `docs/ACTION_ITEMS.md` is the improvement roadmap (items P0.1–P4.3, findings F1–F35). **Whenever you work on an item,
  update its Status (⬜ → 🟡 → ✅) and Notes, and the Progress table counts, in the same commit.** Mention the item ID
  in the commit subject (e.g. `P0.9: fix keyword regex…`).

## Living docs (automated, don't hand-edit the generated parts)

- Hooks live in `.githooks/`; enable once per clone with `bash scripts/install_hooks.sh`.
- **pre-commit** regenerates `docs/KNOWLEDGE_GRAPH.{md,json}`. **post-commit** appends a `docs/CHANGE_LOG.md` entry for
  major commits (touching `app/`, `scripts/`, `tests/`, `.githooks/`, `pyproject.toml`) and amends it into the commit.
  Add `[skip log]` to a commit message to skip the log entry.
- For any non-trivial commit, write a commit **body** explaining *why*: it becomes the entry's "Why / details".
- When you add a new module under `app/`, add it to `STAGE_MAP` in `scripts/update_docs.py` (otherwise it shows as
  "Unmapped" in the graph).
- When capabilities or open issues change, update `docs/PROJECT_OVERVIEW.md` by hand in the same commit.

## Working rules

- Core rule: the LLM edits content; deterministic code owns structure, formatting, validation and file generation.
  Rewrites must stay grounded in evidence from the original resume and must never invent facts.
- Run tests with `.venv_py311/bin/python -m pytest -q` (~35 s; needs `sentence-transformers` installed, see pyproject).
- Never commit secrets or personal output: SSH keys, `.env`, `Claude outputs/`, `data/runs/`, virtualenvs.

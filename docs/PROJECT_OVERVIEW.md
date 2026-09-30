# Project Overview — Resume-optimizer

_Start here. Last reviewed: 2026-09-29 (branch `fb_ksh`). Hand-maintained — update it when capabilities or open
issues change. For "where is X in the code" see [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md); for "what changed when"
see [CHANGE_LOG.md](CHANGE_LOG.md)._

## What it is

A local-first resume tailoring app (Python package `resume-tailor`). You give it a resume (DOCX or PDF) and a pasted
job description, and it:

1. scores how well the resume matches the JD (0–100, with a breakdown),
2. proposes rewrites of your experience bullets that lean toward the JD, **using only facts already in your resume**,
3. lets you review, edit, accept or reject each rewrite, and add extra content in your own words,
4. produces a tailored **DOCX**, **PDF** (via LibreOffice) and **HTML** file, plus an audit log (`changes.md`).

Core rule (from ARCHITECTURE.md): _the LLM edits content; deterministic code owns structure, formatting, validation
and file generation._ Every rewrite must trace back to an "evidence" item from the original resume.

**Ways to run it:** Streamlit UI (`streamlit run app/ui.py`) or CLI (`python -m app.cli analyze|tailor ...`).
**LLM:** Groq cloud (`LLM_PROVIDER=groq`, which is what `.env` uses today) or local Ollama (`qwen3:4b`).
Semantic matching uses a local embedding model (`all-MiniLM-L6-v2`).

## The pipeline

| # | Stage | Main file(s) | What happens |
|---|---|---|---|
| 1 | Ingest | `ingestion/docx.py`, `ingestion/pdf.py` | Reads the file into raw blocks and records where each paragraph lives (`DocumentMap`) |
| 2 | Normalize | `analysis/resume_normalizer.py` | Builds a structured `Resume` + an **evidence ledger**, wrapped in a versioned `ResumeDocument` |
| 3 | JD analysis | `analysis/jd_analyzer.py` | One LLM call returns title, company, seniority, years, requirement lines (by index, so text stays verbatim) and skills; every value is checked against the JD; falls back to heuristics |
| 4 | Match | `analysis/matcher.py`, `analysis/semantic_matcher.py` | Exact / alias / token matching first; embeddings only for what's still missing |
| 5 | Score | `analysis/keyword_match.py`, `analysis/scoring.py` | Keyword match rate (weighted share of JD keywords found) is the headline; requirement-level evidence score kept as secondary |
| 6 | Plan | `analysis/tailor_planner.py` | Chooses which bullets to rewrite and ranks missing requirements |
| 7 | Rewrite | `analysis/rewriter.py` + `llm/client.py` | The LLM rewrites each bullet grounded in its evidence; suggests phrasing for gaps |
| 8 | Validate | `validation/factual.py`, `structural.py`, `output.py` | Rejects rewrites that add new numbers or terms; checks identity and the output files |
| 9 | Render | `rendering/*` | **PRESERVE** (patches your original DOCX in place) or **ATS_DEFAULT** (clean template); PDF via LibreOffice |
| 10 | Report | `services/tailor.py`, `services/run_manager.py` | `changes.md`, artifacts in `data/runs/<id>/`, LLM token usage |

`services/tailor.py::TailorService` orchestrates all of it through three entry points: `analyze_only`,
`generate_proposals` (UI step 1) and `tailor_resume` (UI step 2, "Apply & Generate").

## Capabilities today

| Area | Status | Notes |
|---|---|---|
| DOCX parsing (incl. table layouts) | ✅ Works | Paragraphs and tables in document order, hyperlinks, page-header contact (P1.9) |
| PDF parsing | ✅ Works | Layout-aware (font size, bold, indent, right columns; P1.11). Several roles per company and project sub-sections inside a job (P1.12). The user's resume matches its golden file. Text PDFs only; `ocr.py` is a stub path. PDF input always uses the ATS template |
| JD requirement extraction | ✅ Works | One structured LLM call (title, company, seniority, years, whole-line requirements with priority, skills), every value checked against the JD; deterministic fallback (P1.1) |
| Matching + score | ✅ Works | Headline = keyword match rate with a matched/missing table (P1.2); requirement-level evidence score kept as secondary |
| Tailor content | ✅ Works | All relevant job and project bullets (one call per role), summary, skills order; nothing invented, dropped details flagged (P1.3–P1.7, P1.14) |
| Check parsed resume in UI | ✅ Works | Edit name, headline, contact, links, companies, roles and dates before tailoring (P3.5) |
| Review / edit proposals in UI | ✅ Works | Checkbox + editable text per proposal |
| Gap questions for missing JD keywords | ✅ Works | Suggest-and-confirm: only ticked skills and the user's own answers are added (P3.1) |
| Add free-text content | ✅ Works | Append to an existing role or create a new project |
| Add a **new job role** | ❌ Not built | Designed, see "Open work" |
| Strict Factual Mode | ⚠️ Cosmetic | See issue 4 |
| DOCX / PDF / HTML output | ✅ Works | ATS template (P2.1): A4, Arial, standard headings, section order by experience, "Jan 2022 – Present" dates; files named `First_Last_Resume_<Company>`. PDF needs LibreOffice installed |
| CLI | ✅ Works | `analyze` and `tailor` only; no review step, no addition text |
| Tests | ✅ 233 passing | `pytest -q` (~35 s, loads the cached embedding model) |
| Multiple JDs / history / cover letter | ❌ Not built | — |

## Open issues (found 2026-09-29, not yet fixed)

Ordered by impact. None are fixed yet; they're recorded so they can be prioritized.

1. ~~**Leaked SSH key**~~ (resolved 2026-09-29): a private key (`/Resume-optimizer`) was committed in `4054827` and
   pushed. It was checked and found to be registered nowhere on GitHub (not as a repo deploy key, not as an account
   key), so it never granted access. It's now untracked, gitignored and deleted locally. It still exists in git
   history, so **never register that key anywhere**.
2. **Local Ollama can never work.** The root-level `ollama.py` (a test stub) shadows the real `ollama` package,
   because `app/ui.py` and `app/cli.py` put the repo root first on `sys.path`. Its `list()` returns no models, so
   `LLMClient.is_available()` is always False on the Ollama path and every rewrite silently returns the original text.
   Fix: move the stub under `tests/` (e.g. a `conftest.py` fixture).
3. **UI overrides the Groq model.** The sidebar always passes an Ollama model name (`qwen3:4b`) into
   `LLMClient(model=...)`, which overrides `GROQ_MODEL` when `LLM_PROVIDER=groq`. Groq is then asked for a model it
   doesn't have → calls likely fail → silent no-op rewrites. Needs a quick live confirmation. Fix: make the model
   picker provider-aware.
4. **Strict Factual Mode doesn't change the output.** `tailor_resume()` clears `approved_proposals` (`tailor.py` ~L422)
   *after* the DOCX was already rendered with them (~L391–397) and after they were applied to the resume model.
   It's on by default in the UI.
5. **"Apply & Generate" runs the LLM twice.** `tailor_resume()` always re-runs planner + rewriter (~L298–299) and
   then discards the result in favour of the UI's pre-approved list, which doubles LLM time and tokens.
6. **Dead code:** a duplicate block after `except Exception: pass` in `tailor_resume()` (~L532–539) writes to a
   closed file if reached. `app/services/validation_agent.py` isn't imported anywhere. 5 of 6 prompt files in
   `app/llm/prompts/` are unused (only `rewrite_bullet.txt` is loaded; see KNOWLEDGE_GRAPH §6).
7. **User's source resume** has "LinkedIn | Email | Leetcode" as placeholder text with no hyperlinks. The user will
   fix this in their own file. Since P1.9, hyperlinks (DOCX and PDF) and written-out URLs are picked up as links.

## Open work: "Add as a new Job Role" (designed, approved, not coded)

Gap: `TailorService.incorporate_user_addition()` can only append one bullet to an existing `Experience` or create a
`Project`; there's no way to create a new `Experience`.

- **Backend** (`app/services/tailor.py`): new `add_new_role(resume, evidence_list, job_desc, role_data, description_text)`
  that builds an `Experience` (add it to the `app.domain.resume` import), splits the pasted description into chunks and
  polishes each into its own grounded bullet. Wire it into `tailor_resume()` next to the `addition_text` handling via a
  new `new_role_data: Optional[dict]`, and force `mode = "ATS_DEFAULT"` when present.
- **Frontend** (`app/ui.py`): add "➕ Add as a new Job Role" to `target_labels`. The target selectbox must move
  **outside** `st.form("proposal_review_form")` (forms don't rerun until submit, and the reveal needs an immediate
  rerun). Fields: Company (structurally required, so confirm with the user), Job Title, Location, "currently working
  here" checkbox, Start/End date (`st.date_input`, formatted `%b %Y`; End shows "Present" when current), description
  text area.

## Repo map (docs)

| File | Purpose | Maintained |
|---|---|---|
| `docs/PROJECT_OVERVIEW.md` | This file: what/status/issues/next | By hand |
| `docs/ACTION_ITEMS.md` | Improvement roadmap with live status per item (P0–P4) | By hand, every change |
| `docs/KNOWLEDGE_GRAPH.md` / `.json` | Where everything is: tree, layer × stage matrix, module cards, deps | Auto (pre-commit) |
| `docs/CHANGE_LOG.md` | Timestamped log of major commits | Auto (post-commit) |
| `ARCHITECTURE.md` | Design principles, semantic-matching contract, privacy | By hand |
| `BUILD.md` | Setup, running, tests, hooks | By hand |
| `CLAUDE.md` | Working rules for Claude Code sessions | By hand |

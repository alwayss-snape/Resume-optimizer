# Project Overview — Resume-optimizer

_Start here. Last reviewed: 2026-10-02 (branch `fb_ksh`). Hand-maintained — update it when capabilities or open
issues change. For "where is X in the code" see [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md); for "what changed when"
see [CHANGE_LOG.md](CHANGE_LOG.md)._

## What it is

Tailores, a resume tailoring app (Python package `resume-tailor`; resume text goes to the configured AI provider, Groq's cloud by default). You give it a resume (DOCX or PDF) and a pasted
job description, and it:

1. scores how well the resume matches the JD (0–100, with a breakdown),
2. proposes rewrites of your experience bullets that lean toward the JD, **using only facts already in your resume**,
3. lets you review, edit, accept or reject each rewrite, and add extra content in your own words,
4. produces a tailored **DOCX**, **PDF** (via LibreOffice) and **HTML** file, plus an audit log (`changes.md`).

Core rule (from ARCHITECTURE.md): _the LLM edits content; deterministic code owns structure, formatting, validation
and file generation._ Every rewrite must trace back to an "evidence" item from the original resume.

**Ways to run it:** the web app (`cd web && npm run build`, then `uvicorn app.api.main:app` and open
http://localhost:8000; Phase 5) or the CLI (`python -m app.cli analyze|propose|tailor ...`). The Streamlit UI was
removed in P5.6 after a parity check.
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
| 8 | Validate | `validation/factual.py`, `structural.py`, `output.py` | Rejects rewrites that add new numbers or terms; checks identity; re-parses the output files (ATS round-trip) |
| 9 | Render | `rendering/*` | **ATS_DEFAULT** (clean A4 template, the default) or **PRESERVE** (patches your original DOCX in place; UI "Advanced" option); PDF via LibreOffice |
| 10 | Report | `services/tailor.py`, `services/run_manager.py` | `changes.md`, artifacts in `data/runs/<id>/`, LLM token usage |

`services/tailor.py::TailorService` orchestrates all of it through three entry points: `analyze_only`,
`generate_proposals` (UI step 1) and `tailor_resume` (UI step 2, "Apply & Generate").

## Capabilities today

| Area | Status | Notes |
|---|---|---|
| DOCX parsing (incl. table layouts) | ✅ Works | Paragraphs and tables in document order, hyperlinks, page-header contact (P1.9) |
| PDF parsing | ✅ Works | Layout-aware (font size, bold, indent, right columns; P1.11). Several roles per company and project sub-sections inside a job (P1.12). The user's resume matches its golden file. Text PDFs only; `ocr.py` is a stub path. PDF input always uses the ATS template |
| JD requirement extraction | ✅ Works | One structured LLM call (title, company, seniority, years, whole-line requirements with priority, skills), every value checked against the JD; deterministic fallback (P1.1) |
| Matching + score | ✅ Works | Headline = keyword match rate with a matched/missing table (P1.2), plural- and verb-form-insensitive (P7.2); requirement-level evidence score kept as secondary. Results names the keywords still missing and links to where they can be confirmed (P7.2) |
| Tailor content | ✅ Works | All relevant job and project bullets (one call per role), summary, skills order; nothing invented, dropped details flagged (P1.3–P1.7, P1.14) |
| Check parsed resume in UI | ✅ Works | Edit name, headline, contact, links, companies, roles and dates before tailoring (P3.5); add a job the file was missing or remove a misread one, before drafting so it's tailored and scored too (P7.1) |
| Review / edit proposals in UI | ✅ Works | Side-by-side diff with JD keywords highlighted, status badge, edit box, accept/reject all, match rate recalculated on demand, keyword gap table and score breakdown (P3.4) |
| Gap questions for missing JD keywords | ✅ Works | Suggest-and-confirm: only ticked skills and the user's own answers are added (P3.1); confirmed answers are saved locally and pre-filled for the next JD (P3.2) |
| Content checks on the result | ✅ Works | Bullets per role, length, pronouns, buzzwords, tense, dates, share of bullets with numbers (P2.6); advice only |
| Add free-text content | ✅ Works | Append to an existing role or create a new project |
| Add a **new job role** | ✅ Works | Company, title, location, dates or "currently here", description → fact-checked bullets, placed in date order (P3.3) |
| Strict Factual Mode | ⚠️ Cosmetic | See issue 4 |
| DOCX / PDF / HTML output | ✅ Works | Re-parsed after rendering to prove it reads back intact (ATS round-trip, P2.5). ATS template (P2.1): A4, Arial, standard headings, section order by experience, "Jan 2022 – Present" dates; files named `First_Last_Resume_<Company>`. Auto page-fit to 1 page (< 8 years) or 2, trimming the least relevant content and reporting it (P2.3–P2.4). PDF and page-fit need LibreOffice installed |
| Web API | ✅ Works | FastAPI (P5.1): one endpoint per step, SSE progress, per-visitor sessions with expiry, upload checks, rate limit. Public-hosting hardening is P5.7 |
| Web UI (`web/`) | ✅ Works | React app (P5.2–P5.6) redesigned in Phase 6 as **Editor's Proof** (`DESIGN.md`): bright paper on a light desk with a matching dark mode that follows the system, blue pencil as the one action colour, proof marks for every change (struck, inserted, highlighted keywords, reasons in the margin), a landing hero of 3D proof sheets with self-drawing marks over a WebGL ink field, a score rule instead of a gauge, WCAG 2.2 AA. Flow unchanged: upload → check details → review → results, plus the match report |
| CLI | ✅ Works | `analyze`, `propose` (editable review file) and `tailor --proposals` with the UI's features: edits, gap answers, additions, a new job, strict mode; live progress (P3.6) |
| Tests | ✅ 384 backend + 68 front-end passing | `pytest -q` (~50-80 s); the full offline eval of 8 anonymized cases runs with `pytest -m eval` |
| Evaluation set | ✅ Works | 11 anonymized resume + JD cases with expected facts; `python -m app.eval run --tailor --check` (P4.1, P4.2); LLM-as-judge from another model family, rubric + position-swapped pairwise, `--judge` / `--replay` (P4.3) |
| Arrange and edit after AI changes | ✅ Works | From Results: reorder sections, jobs and each job's bullets (never across jobs), hide sections, reword a bullet, keep what page-fit trimmed, choose 1 / 2 / 3 pages or "don't trim"; re-rendered with no LLM, checked like a tailoring run (P8.13–P8.16) |
| Resumes outside tech, outside the US, not in English | ✅ Works | Unknown sections kept verbatim under their own heading; header details kept; non-tech job-line formats, EU / US numeric dates, seasons, "Till Date"; phone formats worldwide; text boxes; .txt, pasted text, .doc / .odt / .rtf; a content coverage check fails any run that loses a line (P8.1–P8.8, P8.22). Non-English text is kept and named "English only for now" (P8.25) |
| Fair score | ✅ Works | Alternatives, slash terms, acronyms, degree levels, places excluded, skills-only keywords at a quarter credit, perks never keywords, low scores explained, job conditions (licences, shifts, lifting…) as a separate checklist (P8.17–P8.21) |
| Multiple JDs / history / cover letter | ❌ Not built | Backlog in Phase 8 |

## Open issues

Last reviewed 2026-09-30. The 2026-09-29 audit list is resolved: the Ollama stub shadowing (P0.6), the UI passing an
Ollama model name to Groq (P0.2), cosmetic Strict Mode (P0.8), the double LLM run on Apply (P0.7) and the dead code
and unused prompts (P0.8, P1.10) are all fixed. What remains:

1. **Leaked SSH key in git history** (resolved 2026-09-29): a private key committed in `4054827` was registered
   nowhere on GitHub, so it never granted access. It's untracked, gitignored and deleted locally, but still in history,
   so **never register that key anywhere**.
2. **Groq free-tier daily limit (200K tokens/day)** is shared by all development runs; a full real-resume run costs
   ~13K. Live gate runs can be blocked for hours. Local Ollama (`qwen3:4b`) is too heavy for the 8 GB development
   machine; its config fixes are parked in `git stash` ("ollama backup").
3. **Summary years:** the summary states years computed from role dates ("4+ years"), which can differ from a figure written in the resume ("3.6 years"); the judge flags that as a mismatch. Decide whether to keep the computed figure.
4. **User's source resume** has "LinkedIn | Email | Leetcode" placeholder text with no hyperlinks (to fix in their
   own file).
5. **Rewrites can borrow the job's wording** (was P1.15, now P8.9): a fact-checked rewrite added "batch pipeline",
   which appears only in the JD. **Report status vs keywords** (was P1.16, now P8.18): a requirement can read "not
   shown" while all its keywords are found.
6. **Cross-domain user testing (2026-10-02), Phase 8 (all 26 items done 2026-10-03, stages H–L):** 39 findings (U1–U39) from 19 non-tech, non-US and
   non-English personas, including silent section loss, misattributed facts, dropped phone numbers and an unfair
   score. See [user_testing/2026-10-02/FINDINGS.md](user_testing/2026-10-02/FINDINGS.md). Planned in
   [ACTION_ITEMS.md](ACTION_ITEMS.md) as P8.1–P8.26, stages H–L: never lose content (H), honest content (I), an
   **arrange-and-edit step** after the AI changes (J, owner request), a fair score (K), and clear failures and privacy
   (L). Next: the owner reviews the current state; that review and what is left of the Stage L gate are Phase 9 in ACTION_ITEMS.

## Repo map (docs)

| File | Purpose | Maintained |
|---|---|---|
| `docs/PROJECT_OVERVIEW.md` | This file: what/status/issues/next | By hand |
| `PRODUCT.md` / `DESIGN.md` | Product context and the built design system (Impeccable; `.impeccable/` holds the direction contract) | By hand / Impeccable |
| `docs/user_testing/` | User-testing findings and fictional persona inputs to reproduce them | By hand |
| `docs/ACTION_ITEMS.md` | Improvement roadmap with live status per item (P0–P8) | By hand, every change |
| `docs/KNOWLEDGE_GRAPH.md` / `.json` | Where everything is: tree, layer × stage matrix, module cards, deps | Auto (pre-commit) |
| `docs/CHANGE_LOG.md` | Timestamped log of major commits | Auto (post-commit) |
| `ARCHITECTURE.md` | Design principles, semantic-matching contract, privacy | By hand |
| `BUILD.md` | Setup, running, tests, hooks | By hand |
| `CLAUDE.md` | Working rules for Claude Code sessions | By hand |

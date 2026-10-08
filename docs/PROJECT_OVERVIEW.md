# Project Overview — Resume-optimizer

_Start here. Last reviewed: 2026-10-09 (branch `fb_ksh`). Hand-maintained — update it when capabilities or open
issues change. For "where is X in the code" see [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md); for "what changed when"
see [CHANGE_LOG.md](CHANGE_LOG.md)._

## What it is

Tailores, a resume tailoring app (Python package `resume-tailor`; resume text goes to the configured AI provider, Groq's cloud by default). You give it a resume (DOCX, PDF, .doc / .odt / .rtf, .txt or pasted text) and a
pasted job description, and it:

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
| PDF parsing | ✅ Works | Layout-aware (font size, bold, indent, right columns; P1.11). Several roles per company and project sub-sections inside a job (P1.12). The user's resume matches its golden file. A LinkedIn "Save to PDF" profile export is recognised and read by its two-column layout (sidebar and main column apart, durations and page footers dropped; falls back to the normal parse when unsure; P10.1). Text PDFs only; `ocr.py` is a stub path. PDF input always uses the ATS template |
| JD requirement extraction | ✅ Works | One structured LLM call (title, company, seniority, years, whole-line requirements with priority, skills), every value checked against the JD; deterministic fallback (P1.1) |
| Matching + score | ✅ Works | Headline = keyword match rate with a matched/missing table (P1.2), plural- and verb-form-insensitive (P7.2); requirement-level evidence score kept as secondary. Results names the keywords still missing and links to where they can be confirmed (P7.2) |
| Tailor content | ✅ Works | All relevant job and project bullets (one call per role), summary, skills order; nothing invented, dropped details flagged (P1.3–P1.7, P1.14) |
| Check parsed resume in UI | ✅ Works | Edit name, headline, contact, links, companies, roles and dates before tailoring (P3.5); add a job the file was missing or remove a misread one, before drafting so it's tailored and scored too (P7.1) |
| Review / edit proposals in UI | ✅ Works | Side-by-side diff with JD keywords highlighted, status badge, edit box, accept/reject all, match rate recalculated on demand, keyword gap table and score breakdown (P3.4) |
| Gap questions for missing JD keywords | ✅ Works | Suggest-and-confirm: only ticked skills and the user's own answers are added (P3.1); confirmed answers are saved locally and pre-filled for the next JD (P3.2) |
| Content checks on the result | ✅ Works | Bullets per role, length, pronouns, buzzwords, tense, dates, share of bullets with numbers (P2.6); advice only |
| Add free-text content | ✅ Works | Append to an existing role or create a new project |
| Add a **new job role** | ✅ Works | Company, title, location, dates or "currently here", description → fact-checked bullets, placed in date order (P3.3) |
| Choose projects, not lines | ✅ Works | A job with more projects than it keeps (current job 3, older 2) keeps the ones closest to the JD, or the most impactful when the JD is too short to rank by; each choice shows its reason on Review, where any project can be kept or left out. A job added on Check details takes a whole project bank ("Project:" headings, up to 40 lines) (P10.13) |
| Strict Factual Mode | ⚠️ Cosmetic | See issue 4 |
| DOCX / PDF / HTML output | ✅ Works | Re-parsed after rendering to prove it reads back intact (ATS round-trip, P2.5). ATS template (P2.1): A4, Arial, standard headings, section order by experience, "Jan 2022 – Present" dates (US jobs: Letter and "01/2022 – Present", by the region confirmed on Review, P10.3); files named `First_Last_Resume_<Company>`. Auto page-fit to 1 page (< 8 years) or 2, trimming the least relevant content and reporting it (P2.3–P2.4). PDFs are tagged (accessible, P10.4). PDF and page-fit need LibreOffice installed |
| Web API | ✅ Works | FastAPI (P5.1): one endpoint per step, SSE progress, per-visitor sessions with expiry (swept every minute, P9.1), upload checks, rate limit. Every broken upload gets its own plain message, never a 500: damaged, empty, password-protected, scanned, too large, wrong type (P8.22, P9.2). Public-hosting hardening is P5.7 |
| Web UI (`web/`) | ✅ Works | React app (P5.2–P5.6) redesigned in Phase 6 as **Editor's Proof** (`DESIGN.md`): bright paper on a light desk with a matching dark mode that follows the system, blue pencil as the one action colour, proof marks for every change (struck, inserted, highlighted keywords, reasons in the margin), a landing hero of 3D proof sheets with self-drawing marks over a WebGL ink field, a score rule instead of a gauge, WCAG 2.2 AA. Flow unchanged: upload → check details → review → results, plus the match report |
| CLI | ✅ Works | `analyze`, `propose` (editable review file) and `tailor --proposals` with the UI's features: edits, gap answers, additions, a new job, strict mode; live progress (P3.6) |
| Tests | ✅ 655 backend + 99 front-end passing | `pytest -q` (~4 min); the offline eval and persona cases run with `pytest -m eval` (52 pass, no known failures since P10.7). A browser walkthrough in Chrome at 1440 / 390 px, light and dark: `scripts/walkthrough.cjs` (P9.4); `LIVE=1` runs it against the real app and AI (P9.11) |
| Evaluation set | ✅ Works | 11 anonymized resume + JD cases with expected facts; `python -m app.eval run --tailor --check` (P4.1, P4.2); LLM-as-judge from another model family, rubric + position-swapped pairwise, `--judge` / `--replay` (P4.3) |
| Arrange and edit after AI changes | ✅ Works | From Results: reorder sections, jobs and each job's bullets (never across jobs), hide sections, reword a bullet, keep what page-fit trimmed, choose 1 / 2 / 3 pages or "don't trim"; re-rendered with no LLM, checked like a tailoring run (P8.13–P8.16) |
| Resumes outside tech, outside the US, not in English | ✅ Works | Unknown sections kept verbatim under their own heading; header details kept; non-tech job-line formats, EU / US numeric dates, seasons, "Till Date"; phone formats worldwide; text boxes; .txt, pasted text, .doc / .odt / .rtf; a content coverage check fails any run that loses a line (P8.1–P8.8, P8.22). Non-English text is kept and named "English only for now" (P8.25) |
| Fair score | ✅ Works | Alternatives, slash terms ("Compact/NLC", "PL/SQL"), acronyms, degree levels, places excluded, sections kept verbatim (Clinical Rotations, Volunteer) read too (P9.15), skills-only keywords at a quarter credit, perks never keywords, low scores explained, job conditions (licences, shifts, lifting…) as a separate checklist (P8.17–P8.21) |
| Multiple JDs / history / cover letter | ❌ Not built | Backlog in Phase 8 |
| Project notes beside the resume | ✅ Works | A project bank file or pasted notes: new jobs and projects merged in, overviews and figures kept as project evidence, lines the notes doubt ("to verify", superseded) held back and listed (P11.1) |
| Role brief and project choice | ✅ Works | What the job really needs (stated or inferred from its words), a map of which projects show each need with a quote of their own words, projects chosen to cover different needs (P11.3, P11.4) |
| Questions before writing | ✅ Works | A Questions step asks about needs nothing shows yet and projects with no figure; answers become that project's evidence and bullets, saved for next time (P11.2) |
| Project-level writing | ✅ Works | Each project written whole from all its material (built → how → result), every new bullet fact-checked against that material; headline from the job's title as far as the owner's titles support it; Skills rebuilt from evidence (P11.5–P11.7) |
| Classic template | ✅ Works (option) | Company first, rule between jobs, figures in bold, serif; reads back like the standard one (P11.9) |
| Reference eval | 🟡 Built | `python -m app.eval reference <private case>`: Tailores vs another resume, judged both ways round; the live gate waits for the owner's answers (P11.10) |

## Open issues

Last reviewed 2026-09-30. The 2026-09-29 audit list is resolved: the Ollama stub shadowing (P0.6), the UI passing an
Ollama model name to Groq (P0.2), cosmetic Strict Mode (P0.8), the double LLM run on Apply (P0.7) and the dead code
and unused prompts (P0.8, P1.10) are all fixed. What remains:

1. **Leaked SSH key in git history** (resolved 2026-09-29): a private key committed in `4054827` was registered
   nowhere on GitHub, so it never granted access. It's untracked, gitignored and deleted locally, but still in history,
   so **never register that key anywhere**.
2. **Groq free-tier daily limit (200K tokens/day)** is shared by all development runs; a full real-resume run costs
   ~13K; with Phase 11 (notes, brief, project map, project writing, skills) a run with a large project bank costs
   ~27K over about 8 calls, so about 7 such runs a day, and per-minute 429 waits stretch it to ~3 minutes.
   Live gate runs can be blocked for hours. Local Ollama (`qwen3:4b`) is too heavy for the 8 GB development
   machine; its config fixes are parked in `git stash` ("ollama backup").
3. **Summary years** (resolved 2026-10-05, P9.9): the summary reuses the years the resume itself states ("3.6 years",
   "3 years 7 months"); the figure computed from role dates ("4+ years") is used only when the resume states none.
   The user can still edit the summary in Review. Since P11.6 a job added in the run (from notes or on Check
   details) makes the stated figure out of date, and the computed years are used.
4. **LinkedIn export education doesn't read back** (seen 2026-10-09 with both templates): "Bachelor of Engineering -
   BE, Computer Science  2013 – 2017" is rendered but the ATS read-back doesn't find the entry. Pre-existing, not logged
   as an item yet.
5. **User's source resume** has "LinkedIn | Email | Leetcode" placeholder text with no hyperlinks (to fix in their
   own file).
6. **Rewrites can borrow the job's wording** (was P1.15, now P8.9): a fact-checked rewrite added "batch pipeline",
   which appears only in the JD. **Report status vs keywords** (was P1.16, now P8.18): a requirement can read "not
   shown" while all its keywords are found.
7. **Cross-domain user testing (2026-10-02), Phase 8 (all 26 items done 2026-10-03, stages H–L):** 39 findings (U1–U39) from 19 non-tech, non-US and
   non-English personas, including silent section loss, misattributed facts, dropped phone numbers and an unfair
   score. See [user_testing/2026-10-02/FINDINGS.md](user_testing/2026-10-02/FINDINGS.md). Planned in
   [ACTION_ITEMS.md](ACTION_ITEMS.md) as P8.1–P8.26, stages H–L.
8. **Phase 9 close-out (P9.1–P9.5 done 2026-10-04):** the Stage L gate is finished: an independent review of
   P8.22–P8.26 (6 issues fixed, the worst being every section heading added to the output as "Additional
   information"), a timed edge-file sweep with no 500s, a real-browser walkthrough, and a live private run of the
   owner's resume (golden parse, 12/12 bullets handled, 100% coverage, clean read-back, 1 page; Groq per-minute
   limits and reasoning cut-offs are now retried instead of losing bullets). **Next (accepted 2026-10-05):** stages M–Q
   in ACTION_ITEMS: quick fixes (drafting screen, no web data kept in `data/runs/`, summary years), the live coverage
   runs, LinkedIn import, output formats (US Letter / region, tagged PDF, Academic CV and Federal templates), then a
   cover letter and opt-in local history. OCR stays in the backlog. **Stage M done; Stage N in progress
   (2026-10-05):** the landing page's two actions now follow the inputs (P9.14); live persona runs for nurse, sales-pdf
   and india found seven real problems, all fixed (P9.15–P9.21: custom sections and slash words in the match, usage
   counted twice, a repeated "Skills:" label, unchanged bullets listed as rewrites, a comma title read back wrong, a
   city kept in the company); the live-AI browser walkthrough passed (P9.11). **Stage N done (2026-10-06):** eu_cv passes (German kept verbatim); academic found three more problems, all fixed (P9.23 JD skills matched inside longer words, P9.24 a current job's bullets turned into the past tense, P9.25 "Grants And Funding"); its 3 pages wait for the Academic CV template (P10.6). Private live run clean. **Stage O (2026-10-07):** LinkedIn "Save to PDF" import built (P10.1) against an anonymized fixture and golden file; gate passed. **Stage P, output formats (P10.2–P10.7), in progress:** one page spec (A4 or US Letter) drives the DOCX, the HTML preview and page-fit (P10.2). The region is suggested from the JD with its evidence, confirmed on Review and switchable in Arrange: US gets Letter and 01/2022 dates; personal details get advice for US / UK / EU jobs (P10.3). PDFs are tagged for screen readers (P10.4). The CV type (standard, Academic CV, US Federal) is suggested from resume and JD signals and confirmed by the user; academic and federal have no page cap (P10.5). The Academic CV uses CV order, "Academic Appointments", appointments listed under Education moved to jobs, and publications word for word and numbered (P10.6). The US Federal resume prints each job's fields (hours, salary, series / grade, supervisor) on their own lines, word for word, in USAJOBS order; header and job field lines now count for keyword matching (P10.7). Groq strict-JSON rejections that repeat now fall back to plain JSON mode with a readable error (P9.22).
9. **Groq free tier, per minute:** 8K tokens per minute means role rewrites can wait 30–60 s each on a busy run.
   That is now waited out (shown as progress), so a real run takes ~1–2 minutes of drafting. The same cap can leave a long role's answer
   out of completion tokens on every try; such a role is now retried in two halves (P10.10).

## Repo map (docs)

| File | Purpose | Maintained |
|---|---|---|
| `docs/PROJECT_OVERVIEW.md` | This file: what/status/issues/next | By hand |
| `PRODUCT.md` / `DESIGN.md` | Product context and the built design system (Impeccable; `.impeccable/` holds the direction contract) | By hand / Impeccable |
| `docs/user_testing/` | User-testing findings and fictional persona inputs to reproduce them | By hand |
| `docs/ACTION_ITEMS.md` | Improvement roadmap with live status per item (P0–P9) | By hand, every change |
| `docs/KNOWLEDGE_GRAPH.md` / `.json` | Where everything is: tree, layer × stage matrix, module cards, deps | Auto (pre-commit) |
| `docs/CHANGE_LOG.md` | Timestamped log of major commits | Auto (post-commit) |
| `ARCHITECTURE.md` | Design principles, semantic-matching contract, privacy | By hand |
| `BUILD.md` | Setup, running, tests, hooks | By hand |
| `CLAUDE.md` | Working rules for Claude Code sessions | By hand |

# Change Log — Resume-optimizer

Timestamped record of every **major** commit (anything touching `app/`, `scripts/`, `tests/`, `.githooks/` or
`pyproject.toml`), newest first. Entries are written automatically by the post-commit hook
(`scripts/update_docs.py log-entry`); docs-only commits and commits containing `[skip log]` are skipped.

- **Why** comes from the commit message body, so write one for anything non-trivial.
- **Structure delta** is computed from the code itself: classes and functions added or removed.
- You may hand-edit an entry to add context; the hook only rewrites an entry when that same commit is amended.

<!-- entries below; newest first -->

<!-- entry:2026-09-30T16:32:49+05:30 -->
## 2026-09-30 16:32 (+0530) · P0.7 + P0.8: Stop re-running the rewriter on Apply; make Strict Mode real

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> P0.7: when the UI passes user-approved proposals, tailor_resume used to
> re-run the full LLM rewrite pass and then discard it, doubling LLM time and
> tokens. The deterministic planner still runs (plan.json, unsupported
> requirements), but execute_plan is now skipped.
>
> P0.8: Strict Factual Mode cleared approved proposals only after the DOCX
> had been rendered with them, so the output kept rewrites the report said
> were withheld. The all-or-nothing decision (any rejected rewrite or
> structural change -> roll back every rewrite, including evidence) now
> happens before rendering, and revisions are recorded only for what's kept.
> changes.md no longer overwrites its progress log and writes one final
> summary (previously two copies plus unreachable writes after `except`).
>
> The UI now defaults Strict Mode to off: until the validator is rebalanced
> (P1.8) it rejects most good rewrites, so a working all-or-nothing mode
> would withhold nearly everything. Failing rewrites are still dropped
> individually with it off.
>
> Also adds tests/conftest.py pinning tests to an unreachable local provider:
> the developer's .env (LLM_PROVIDER=groq + key) was making the suite call
> Groq live. Suite time 47-80 s -> 17 s.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Entry points: `M` app/ui.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/conftest.py, `A` tests/unit/test_tailor_resume_flow.py

---

<!-- entry:2026-09-30T16:30:03+05:30 -->
## 2026-09-30 16:30 (+0530) · Treat any .py file as a major change for the change log

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Root-level Python files (like the removed ollama.py) were not matched by the folder prefixes, so their commits got no CHANGE_LOG entry.

**Changed files**

- Tooling: `M` scripts/update_docs.py

---

---

<!-- entry:2026-09-30T16:29:51+05:30 -->
## 2026-09-30 16:29 (+0530) · P0.6: Remove root ollama.py stub that shadowed the real package

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> app/ui.py and app/cli.py put the repo root first on sys.path, so
> `import ollama` resolved to this test stub, whose list() returns no models.
> LLMClient.is_available() was therefore always False on the Ollama path and
> every rewrite silently fell back to the original text. The real ollama
> package (0.6.2) is installed; tests patch ollama.Client on it directly,
> so no replacement shim is needed.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Root: `D` ollama.py

---

---

---

<!-- entry:2026-09-30T16:29:11+05:30 -->
## 2026-09-30 16:29 (+0530) · P0.9: Fix score cap at 60, empty JD keywords, and unit-blind number check

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> - Scoring: calculate_score hard-weighted required/preferred/keyword buckets
>   at 0.6/0.3/0.1 even when a bucket was empty, so a perfect match scored
>   60/100. It now renormalises over buckets that contain requirements, and
>   JDAnalyzer sets criticality from the detected priority so preferred
>   requirements land in the preferred bucket.
> - JD keywords: the regex was double-escaped (matched a literal backslash),
>   so keywords were always empty and never reached the rewrite prompt.
>   Replaced with a stopgap that keeps only technical-looking terms (acronyms,
>   C++/C#/Node.js/CI-CD style tokens, mid-sentence capitalised words, known
>   multi-word terms). P1.1 replaces this with LLM skill extraction.
> - FactualValidator: numbers with unit suffixes (2M, 40K, 10x, 1,000+) were
>   invisible, so "2M events" -> "5M events" passed validation.

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py, `M` app/analysis/scoring.py
- Docs: `M` docs/ACTION_ITEMS.md
- Tests: `M` tests/unit/test_jd_analyzer.py, `M` tests/unit/test_scoring.py, `M` tests/unit/test_validation.py
- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/analysis/scoring.py`: added `AlignmentScorer._compute()`

---

---

---

---

<!-- entry:2026-09-29T22:59:34+05:30 -->
## 2026-09-29 22:59 (+0530) · Add self-updating knowledge graph, change log and project overview

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The project's docs were spread across five overlapping files that
> contradicted each other (e.g. "V1 complete, 59 tests" vs 87 passing), and
> there was no reliable map of where things live or record of what changed.
>
> - scripts/update_docs.py (stdlib only, deterministic): generates
>   docs/KNOWLEDGE_GRAPH.{md,json} from the code's AST. It includes the
>   directory map, a layer x pipeline-stage matrix, module cards with
>   imports/imported-by/tested-by, a dependency diagram, config keys, prompt
>   usage, and gaps (untested/orphan modules). It also writes
>   docs/CHANGE_LOG.md entries, backfilled here from all 39 major commits.
> - .githooks/: pre-commit regenerates the graph, and post-commit adds a
>   change-log entry for major commits and amends it in (index changes made
>   in commit-msg are not picked up). The hooks never block a commit.
>   Enable per clone with scripts/install_hooks.sh.
> - docs/PROJECT_OVERVIEW.md replaces STATUS.md as the "start here" doc:
>   capabilities, open issues found in this review, and the add-job-role design.
> - Removed STATUS.md, MEMORY.md and CHANGELOG.md; their content was carried
>   into the new docs.
> - Repo hygiene: untracked the committed SSH deploy key and .venv_py311/,
>   deleted the stray =2.1.0 / =7.4.0 files, and gitignored secrets and
>   "Claude outputs/". The key is still in history and must be revoked on GitHub.

**Changed files**

- Docs: `A` docs/PROJECT_OVERVIEW.md
- Root: `M` .gitignore, `D` =2.1.0, `D` =7.4.0, `M` BUILD.md, `D` CHANGELOG.md, `A` CLAUDE.md, `D` MEMORY.md, `M` README.md, `D` Resume-optimizer, `D` Resume-optimizer.pub, `D` STATUS.md
- Tooling: `A` .githooks/_python, `A` .githooks/post-commit, `A` .githooks/pre-commit, `A` scripts/install_hooks.sh, `A` scripts/update_docs.py
- _(+7561 virtualenv files omitted)_

**Structure delta**

- new module `scripts/update_docs.py`

---

---

---

---

---

<!-- entry:2026-09-29T15:37:29+00:00 -->
## 2026-09-29 21:07 (+0530) · Polish resume output formatting (DOCX/PDF + HTML preview)

`1925946` · Kshitij Chaubey

**Why / details**

> The downloaded PDF is generated from template_renderer.py's DOCX output
> via LibreOffice (not from html_renderer.py, which only backs the in-app
> browser preview) -- both needed fixing since the DOCX output is what the
> user actually sees as their tailored_resume.pdf.
>
> template_renderer.py:
> - Tighter margins (0.6"/0.5") and consistent Calibri typography instead
>   of python-docx's default Normal style.
> - Section headings now render as an accent-colored, bold, uppercase label
>   with a bottom-border rule (added via raw OOXML -- python-docx has no
>   high-level paragraph-border API) instead of a plain default Word
>   Heading 1 style.
> - Experience/education entries now use the standard modern-resume layout:
>   title/degree (bold) on the left with the date range right-aligned on
>   the SAME line via a right tab stop, company/institution + location on
>   the line below in italic gray -- instead of stacking title-with-dates
>   and company-with-location as two plain left-aligned lines.
> - Bold category labels in the skills section, spacing cleanup throughout.
>
> html_renderer.py:
> - Same entry-head layout (title left / dates right, flexbox) and italic
>   meta line, so the browser preview and the DOCX/PDF download read as the
>   same design instead of two different products.
> - Added a missing Achievements section (data was already flowing through
>   after the resume_normalizer fix but had no renderer output).
>
> Verified: rendered the user's real resume through both renderers,
> converted the DOCX to PDF via LibreOffice and the HTML through a real
> headless-Chromium page render (not LibreOffice's limited HTML->PDF path,
> which doesn't respect flexbox) -- both inspected visually. Existing
> html_renderer/docx_parser/resume_normalizer tests still pass (4/4); added
> 3 new template_renderer tests since the existing docx_renderer test file
> pulls in the LLM rewriter's full import chain.

**Changed files**

- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/template_renderer.py
- Tests: `A` tests/unit/test_template_renderer_standalone.py

**Structure delta**

- `app/rendering/html_renderer.py`: added `HtmlResumeRenderer._meta_line()`
- `app/rendering/template_renderer.py`: added `TemplateRenderer._add_bottom_border()`, `TemplateRenderer._add_section_heading()`, `TemplateRenderer._add_title_dates_line()`, `TemplateRenderer._content_width()`, `TemplateRenderer._set_document_defaults()`

---

---

---

---

---

---

<!-- entry:2026-09-29T15:25:45+00:00 -->
## 2026-09-29 20:55 (+0530) · Use LLM to identify genuine JD requirements instead of naive line-splitting

`3b81757` · Kshitij Chaubey

**Why / details**

> Previously, JDAnalyzer split a pasted job description on raw newlines and
> flagged a line as a "requirement" if it was a bullet OR matched one of a
> broad set of generic verb/noun signals (experience, develop, manage,
> build, ...). In practice this meant:
>
> - Hard-wrapped JDs (copy-pasted from job boards at a fixed column width)
>   shredded a single requirement sentence into unrelated-looking fragments
>   scored independently.
> - Any bulleted line anywhere in the JD -- including benefits/perks,
>   company culture blurbs, and EEO statements -- got treated as a
>   requirement just for being a bullet, since REQUIREMENT_SIGNALS is broad
>   enough to match most ordinary business prose too.
>
> Fixes:
> - Added a line-reflow pass (_reflow_lines) that rejoins a wrapped
>   continuation line into the previous line before scoring, using "starts
>   lowercase + previous line has no clause-ending punctuation" as the
>   signal (avoids merging short label lines like "Company: Acme Inc.",
>   which start uppercase).
> - Added an LLM-assisted selection pass (_llm_select_requirement_lines):
>   when an LLM client is configured and reachable, it's asked to pick
>   which line INDICES (never freeform text) are genuine requirements vs
>   boilerplate. Because selection is by index into lines we already have,
>   every kept requirement is still guaranteed to be one of the exact lines
>   pulled from the JD -- this preserves the "verbatim from JD" auditability
>   property, it does not let the LLM generate/paraphrase requirement text.
> - Falls back fully to the existing deterministic heuristic when no LLM is
>   configured, it's unreachable, the call errors, or the response looks
>   degenerate (empty selection over a non-trivial candidate pool).
>
> Verified against the 3 existing jd_analyzer tests (still passing) plus 7
> new tests covering reflow correctness and the LLM selection/fallback
> paths (mocked LLM client, since this sandbox's network policy blocks
> outbound calls to api.groq.com -- confirmed via the agent proxy status
> endpoint, not an application bug).

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py
- LLM: `M` app/llm/schemas.py
- Tests: `A` tests/unit/test_jd_analyzer_llm.py

**Structure delta**

- `app/analysis/jd_analyzer.py`: added `JDAnalyzer._llm_select_requirement_lines()`, `JDAnalyzer._reflow_lines()`
- `app/llm/schemas.py`: added `class JDRequirementSelection`

---

---

---

---

---

---

<!-- entry:2026-09-29T15:18:47+00:00 -->
## 2026-09-29 20:48 (+0530) · Fix resume parsing data-integrity bugs found against real resume

`336a106` · Kshitij Chaubey

**Why / details**

> - Strip trailing "|" from titles when dates are separated by " | "
>   instead of ",", which was baking literal pipe characters into every
>   job title (e.g. "Data Scientist II |").
> - Split skills/interests/certifications on commas without breaking
>   parenthetical sub-lists, so "Python (pandas, scikit-learn,
>   transformers)" stays one skill instead of shredding into fragments.
> - Bucket Interests/Awards/Certifications content by the section
>   heading instead of the individual line's own text, fixing Interests
>   being misfiled as a Certification.
> - Extract candidate location from pipe-separated contact header lines
>   (e.g. "LinkedIn | Email | Leetcode | +91-... | Bangalore, India").
> - Wire achievements through to the rendered Resume (previously parsed
>   but silently dropped).
> - Fix bullet glyph handling ("●" and friends) and add location fields
>   to Experience/Education plus an Interests section to both renderers.
>
> Verified against the user's real resume + the existing normalizer/
> docx/html-renderer test suite (4/4 passing).

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Domain models: `M` app/domain/resume.py
- Ingestion: `M` app/ingestion/docx.py
- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/template_renderer.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._extract_date_range()`, `ResumeNormalizer._parse_title_and_dates()`, `ResumeNormalizer._split_respecting_parens()`, `ResumeNormalizer._strip_date_range()`

---

---

---

---

---

---

<!-- entry:2026-08-31T23:04:38+00:00 -->
## 2026-09-01 04:34 (+0530) · Add optional Groq cloud LLM provider; track per-run token usage

`e7a9b34` · Kshitij Chaubey

**Why / details**

> LLMClient now supports a "groq" provider alongside the existing local
> Ollama path, selected via LLM_PROVIDER (default stays "ollama"). Groq
> calls go through httpx against its OpenAI-compatible chat/completions
> endpoint - no new SDK, no change to any caller's generate()/generate_json()
> usage. Default Groq model is openai/gpt-oss-120b (llama-3.3-70b-versatile
> was decommissioned by Groq on 2026-08-16, caught before it shipped).
>
> Also adds usage tracking: every generate() call is now logged on the
> client instance (provider, model, tokens, duration, success/failure),
> aggregated via get_usage_summary(), and saved per run to
> data/runs/<run_id>/llm_usage.json plus a short summary in changes.md -
> so free-tier rate-limit headroom is measured from real runs instead of
> estimated.
>
> Docs (README/ARCHITECTURE/BUILD/CHANGELOG) updated to reflect that
> enabling Groq sends resume/JD text off-device, a deliberate opt-out of
> the project's local-first default.

**Changed files**

- Config: `M` app/config/settings.py
- LLM: `M` app/llm/client.py
- Root: `M` .env.example, `M` ARCHITECTURE.md, `M` BUILD.md, `M` CHANGELOG.md, `M` README.md, `M` pyproject.toml
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_llm_client.py

**Structure delta**

- `app/llm/client.py`: added `LLMClient._generate_groq()`, `LLMClient._generate_ollama()`, `LLMClient._groq_is_available()`, `LLMClient.get_usage_summary()`

---

---

---

---

---

---

<!-- entry:2026-08-31T22:40:35+00:00 -->
## 2026-09-01 04:10 (+0530) · Fix broken Apply & Generate flow and silent no-op rewrites

`0c7d2d8` · Kshitij Chaubey

**Why / details**

> - app/ui.py: drive the tailor flow off st.session_state (idle -> proposals
>   -> results) instead of one-shot st.button return values. The review
>   form's submit button triggers a script rerun on which the outer
>   st.button was no longer True, so the whole Apply & Generate branch
>   (scoring, rendering, preview) was silently skipped every time.
> - app/analysis/rewriter.py: rewrite_bullet() now calls generate_json
>   against the prompt's actual JSON contract instead of treating raw LLM
>   text as the bullet, and returns a rationale that's threaded into each
>   ChangeProposal and shown in the review UI. Add
>   suggest_for_missing_requirement() for advisory-only "what to add"
>   phrasing on JD requirements the resume doesn't cover.
> - app/analysis/tailor_planner.py: rank_missing_requirements() to surface
>   the highest-priority unmet requirements for those suggestions.
> - app/services/tailor.py: incorporate_user_addition() folds a free-text
>   addition (project/achievement/skill) into the resume as a grounded,
>   JD-aware bullet; tailor_resume() now rebuilds the evidence ledger and
>   rescores after applying rewrites + the addition, so the reported
>   alignment score reflects the actual tailoring instead of the
>   pre-tailoring baseline.
> - Add/extend tests covering the JSON-parsing path, missing-requirement
>   suggestions, addition placement, and score recomputation; verified the
>   full upload -> tailor -> review -> apply -> results flow headlessly via
>   streamlit.testing.v1.AppTest.

**Changed files**

- Analysis: `M` app/analysis/rewriter.py, `M` app/analysis/tailor_planner.py
- Entry points: `M` app/ui.py
- LLM: `M` app/llm/schemas.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/integration/test_end_to_end.py, `M` tests/unit/test_rewriter.py, `A` tests/unit/test_tailor_service_addition.py

**Structure delta**

- `app/analysis/rewriter.py`: added `LLMRewriter.suggest_for_missing_requirement()`
- `app/analysis/tailor_planner.py`: added `TailoringPlanner.rank_missing_requirements()`
- `app/llm/schemas.py`: added `class BulletRewriteResult`, `class MissingRequirementSuggestion`
- `app/services/tailor.py`: added `TailorService.incorporate_user_addition()`
- `app/ui.py`: added `_cleanup_session_state()`

---

---

---

---

---

---

<!-- entry:2026-08-31T21:33:07+05:30 -->
## 2026-08-31 21:33 (+0530) · Add semantic matching layer; fix PDF/JD/matcher/scoring bugs

`b4486f9` · Kshitij Chaubey

**Why / details** _(from the retired CHANGELOG.md / MEMORY.md)_

> Added a secondary, embedding-based semantic matcher (`all-MiniLM-L6-v2`) that runs **only** on requirements the deterministic matcher leaves `MISSING`, never overrides a deterministic match, and is excluded from the headline score (surfaced separately as `semantic_coverage`) so an inferred paraphrase is never counted as hard evidence. Fails soft if `sentence-transformers` is missing.
> While validating against a real JD + resume, fixed: (1) PDF word-wrap truncation: every wrapped line became its own block, so long bullets were cut into fragments. Now merged when the next line starts lowercase. (2) JD heading leakage: "Minimum Qualifications"-style headings were extracted as fake requirements, and an over-escaped regex matched a literal `\s`. (3) "AWS/GCP" was treated as requiring both, not either. (4) Scoring: default `criticality == "required"` was never bucketed as required, so most requirements were mis-scored (this intentionally changed score outputs). (5) The planner now labels semantic-only rewrite rationales as "inferred".
> Also made `terminology.py` the single alias map (the matcher had a duplicate) and removed the unused `evidence_index.py` scaffolding.

**Changed files**

- Analysis: `D` app/analysis/evidence_index.py, `M` app/analysis/jd_analyzer.py, `M` app/analysis/matcher.py, `M` app/analysis/scoring.py, `A` app/analysis/semantic_matcher.py, `M` app/analysis/tailor_planner.py, `M` app/analysis/terminology.py
- Config: `M` app/config/settings.py
- Domain models: `M` app/domain/report.py
- Entry points: `M` app/ui.py
- Ingestion: `M` app/ingestion/pdf.py
- Root: `M` ARCHITECTURE.md, `M` CHANGELOG.md, `M` MEMORY.md, `M` README.md, `M` pyproject.toml
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_jd_analyzer.py, `M` tests/unit/test_matcher.py, `M` tests/unit/test_pdf_parser.py, `A` tests/unit/test_scoring.py, `A` tests/unit/test_semantic_matcher.py, `M` tests/unit/test_tailor_planner.py

**Structure delta**

- removed module `app/analysis/evidence_index.py`
- `app/analysis/matcher.py`: added `EvidenceMatcher._extract_requirement_units()`
- new module `app/analysis/semantic_matcher.py`: `class SemanticMatcher`
- `app/analysis/terminology.py`: added `flat_alias_to_canonical()`
- `app/ingestion/pdf.py`: added `PdfParser._merge_wrapped_lines()`

---

---

---

---

---

---

<!-- entry:2026-08-31T19:17:02+05:30 -->
## 2026-08-31 19:17 (+0530) · feat: ChangeProposal review flow, terminology/evidence indexing, scorer breakdown, UI PDF fallback, realtime changes.md; tests updated

`b0704f0` · Kshitij Chaubey

**Why / details** _(from the retired CHANGELOG.md / MEMORY.md)_

> Introduced the `ChangeProposal` schema and the Streamlit review flow (generate, review, edit, then apply proposals), the terminology registry, the deterministic scorer breakdown (`ScoreComponents`), a PDF preview fallback chain (`st.pdf`, then a local HTTP iframe, then a PNG raster) and real-time `changes.md` progress logging.

**Changed files**

- Analysis: `A` app/analysis/change_proposal.py, `A` app/analysis/evidence_index.py, `M` app/analysis/jd_analyzer.py, `M` app/analysis/resume_normalizer.py, `M` app/analysis/rewriter.py, `M` app/analysis/scoring.py, `A` app/analysis/terminology.py
- Domain models: `M` app/domain/evidence.py, `M` app/domain/job.py
- Entry points: `M` app/ui.py
- Rendering: `M` app/rendering/docx_patcher.py
- Root: `M` CHANGELOG.md, `M` README.md
- Services: `M` app/services/tailor.py
- Tests: `A` tests/integration/test_preserve_rewrite_end_to_end.py
- Tooling: `A` scripts/autocommit.sh
- Validation: `M` app/validation/factual.py

**Structure delta**

- new module `app/analysis/change_proposal.py`: `class ChangeProposal`
- new module `app/analysis/evidence_index.py`: `class EvidenceIndex`
- `app/analysis/jd_analyzer.py`: added `JDAnalyzer._segment_line()`
- `app/analysis/rewriter.py`: removed `class RewriteProposal`
- `app/analysis/scoring.py`: added `AlignmentScorer.calculate_components()`, `class ScoreComponents`
- new module `app/analysis/terminology.py`
- `app/services/tailor.py`: added `TailorService.generate_proposals()`
- `app/ui.py`: added `display_pdf_with_fallback()`

---

---

---

---

---

---

<!-- entry:2026-08-31T16:56:49+05:30 -->
## 2026-08-31 16:56 (+0530) · Fix PDF preview for Chrome and related resume rendering updates

`51c86ba` · Kshitij Chaubey

**Changed files**

- Analysis: `M` app/analysis/matcher.py
- Entry points: `M` app/ui.py
- Rendering: `M` app/rendering/template_renderer.py

**Structure delta**

- `app/rendering/template_renderer.py`: added `TemplateRenderer.render_ats_default()`, `class TemplateRenderer`
- `app/ui.py`: added `get_local_pdf_preview_url()`

---

---

---

---

---

---

<!-- entry:2026-08-31T16:16:32+05:30 -->
## 2026-08-31 16:16 (+0530) · fix: PDF parsing - safe PyMuPDF import; update dependency name; remove undefined var

`d8cb977` · Kshitij Chaubey

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Ingestion: `M` app/ingestion/pdf.py
- Root: `M` pyproject.toml
- Services: `M` app/services/tailor.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer.normalize()`, `class ResumeNormalizer`
- `app/ingestion/pdf.py`: added `PdfParser._ensure_fitz()`

---

---

---

---

---

---

<!-- entry:2026-08-31T16:11:26+05:30 -->
## 2026-08-31 16:11 (+0530) · Fix: resolve merge markers in TailorService return payload

`8f97080` · Kshitij Chaubey

**Changed files**

- Services: `M` app/services/tailor.py

**Structure delta**

- `app/services/tailor.py`: added `TailorService.__init__()`, `TailorService.analyze_only()`, `TailorService.generate_preview_md()`, `TailorService.tailor_resume()`, `class TailorService`

---

---

---

---

---

---

<!-- entry:2026-08-31T16:00:16+05:30 -->
## 2026-08-31 16:00 (+0530) · WIP: save local changes before rebase

`4054827` · Kshitij Chaubey

**Why / details** _(from the retired CHANGELOG.md / MEMORY.md)_

> ⚠️ This commit also accidentally added the private SSH deploy key (`Resume-optimizer`) and its `.pub` to the repo. They were untracked on 2026-09-29, but the key remains in history on `origin` and **must be revoked on GitHub**.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Domain models: `M` app/domain/resume_document.py
- LLM: `M` app/llm/client.py, `M` app/llm/prompts/rewrite_bullet.txt
- Root: `A` =2.1.0, `A` =7.4.0, `A` Resume-optimizer, `A` Resume-optimizer.pub, `A` ollama.py
- Tests: `M` tests/unit/test_resume_normalizer.py
- _(+7561 virtualenv files omitted)_

**Structure delta**

- `app/analysis/resume_normalizer.py`: removed `ResumeNormalizer.normalize()`, `class ResumeNormalizer`

---

---

---

---

---

---

<!-- entry:2026-08-31T15:48:16+05:30 -->
## 2026-08-31 15:48 (+0530) · Refactor: renderer accepts ResumeDocument; Tailor passes ResumeDocument; add validation agent and tests

`cd06cb2` · Kshitij Chaubey

**Changed files**

- Analysis: `M` app/analysis/matcher.py
- Rendering: `M` app/rendering/template_renderer.py
- Root: `M` CHANGELOG.md, `M` MEMORY.md
- Services: `M` app/services/tailor.py, `A` app/services/validation_agent.py
- Tests: `M` tests/unit/test_docx_renderer.py
- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/analysis/matcher.py`: added `EvidenceMatcher.__init__()`, `EvidenceMatcher._extract_key_tokens()`, `EvidenceMatcher._meaningful_tokens()`, `EvidenceMatcher._normalize_text()`, `EvidenceMatcher.match()`, `class EvidenceMatcher`
- `app/rendering/template_renderer.py`: removed `TemplateRenderer.render_ats_default()`, `class TemplateRenderer`
- new module `app/services/validation_agent.py`: `class ValidationAgent`
- `app/validation/factual.py`: added `FactualValidator._canonical_term()`, `FactualValidator._factual_terms()`, `FactualValidator.extract_numbers()`, `FactualValidator.validate_proposal()`, `class ClaimCheck`, `class FactualValidator`, `class ValidationResult`

---

---

---

---

---

---

<!-- entry:2026-08-31T14:34:17+05:30 -->
## 2026-08-31 14:34 (+0530) · Phase1: wire StructuralValidator, enforce Strict Factual Mode from UI, include validation warnings in report

`6221d73` · Kshitij Chaubey

**Changed files**

- Entry points: `M` app/ui.py
- Services: `M` app/services/tailor.py

---

---

---

---

---

---

<!-- entry:2026-08-31T14:33:01+05:30 -->
## 2026-08-31 14:33 (+0530) · Phase1: wire StructuralValidator and OutputQAValidator into TailorService; collect validation warnings

`2261605` · Kshitij Chaubey

**Changed files**

- Services: `M` app/services/tailor.py

**Structure delta**

- `app/services/tailor.py`: removed `TailorService.__init__()`, `TailorService.analyze_only()`, `TailorService.generate_preview_md()`, `TailorService.tailor_resume()`, `class TailorService`

---

---

---

---

---

---

<!-- entry:2026-08-31T14:31:10+05:30 -->
## 2026-08-31 14:31 (+0530) · Phase0: fix token/numeric regexes, add dependency check, update MEMORY & CHANGELOG

`74f5133` · Kshitij Chaubey

**Why / details** _(from the retired CHANGELOG.md / MEMORY.md)_

> Baseline restoration for the V2 workstream: fixed the token and numeric regexes used by claim validation and added `scripts/check_dependencies.py` (LibreOffice and Ollama presence).

**Changed files**

- Analysis: `M` app/analysis/matcher.py
- Root: `M` CHANGELOG.md, `M` MEMORY.md
- Tooling: `A` scripts/check_dependencies.py
- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/analysis/matcher.py`: removed `EvidenceMatcher.__init__()`, `EvidenceMatcher._extract_key_tokens()`, `EvidenceMatcher._meaningful_tokens()`, `EvidenceMatcher._normalize_text()`, `EvidenceMatcher.match()`, `class EvidenceMatcher`
- `app/validation/factual.py`: removed `FactualValidator._canonical_term()`, `FactualValidator._factual_terms()`, `FactualValidator.extract_numbers()`, `FactualValidator.validate_proposal()`, `class ClaimCheck`, `class FactualValidator`, `class ValidationResult`
- new module `scripts/check_dependencies.py`

---

---

---

---

---

---

<!-- entry:2026-08-30T19:10:52+05:30 -->
## 2026-08-30 19:10 (+0530) · Render all canonical resume sections in ATS DOCX

`24b1435` · alwayss-snape

**Changed files**

- Rendering: `M` app/rendering/template_renderer.py

---

---

---

---

---

---

<!-- entry:2026-08-30T19:10:35+05:30 -->
## 2026-08-30 19:10 (+0530) · Patch the correct paragraph in table resume cells

`51762e1` · alwayss-snape

**Changed files**

- Rendering: `M` app/rendering/docx_patcher.py

---

---

---

---

---

---

<!-- entry:2026-08-30T19:10:27+05:30 -->
## 2026-08-30 19:10 (+0530) · Parse table cell paragraphs without flattening

`a4be27e` · alwayss-snape

**Changed files**

- Ingestion: `M` app/ingestion/docx.py

---

---

---

---

---

---

<!-- entry:2026-08-30T19:10:12+05:30 -->
## 2026-08-30 19:10 (+0530) · Track paragraph locations inside DOCX table cells

`83de8ba` · alwayss-snape

**Changed files**

- Rendering: `M` app/rendering/document_map.py

---

---

---

---

---

---

<!-- entry:2026-08-30T19:08:08+05:30 -->
## 2026-08-30 19:08 (+0530) · Use ATS HTML preview when PDF is unavailable

`cc02a1d` · alwayss-snape

**Changed files**

- Entry points: `M` app/ui.py

---

---

---

---

---

---

<!-- entry:2026-08-30T19:07:44+05:30 -->
## 2026-08-30 19:07 (+0530) · Render canonical resume as ATS HTML artifact

`5ecaa31` · alwayss-snape

**Changed files**

- Services: `M` app/services/tailor.py

---

---

---

---

---

---

<!-- entry:2026-08-30T19:07:20+05:30 -->
## 2026-08-30 19:07 (+0530) · Test ATS HTML resume rendering

`fe004d3` · alwayss-snape

**Changed files**

- Tests: `A` tests/unit/test_html_renderer.py

---

---

---

---

---

---

<!-- entry:2026-08-30T19:07:11+05:30 -->
## 2026-08-30 19:07 (+0530) · Add ATS-safe HTML resume renderer

`ee61c07` · alwayss-snape

**Why / details** _(from the retired CHANGELOG.md / MEMORY.md)_

> V2 redesign Phase 2: a standard ATS-safe HTML/CSS resume output. Tailoring writes `resume_document.json` and `tailored_resume.html`, and the UI previews the HTML when PDF conversion is unavailable.

**Changed files**

- Rendering: `A` app/rendering/html_renderer.py

**Structure delta**

- new module `app/rendering/html_renderer.py`: `class HtmlResumeRenderer`

---

---

---

---

---

---

<!-- entry:2026-08-30T19:06:22+05:30 -->
## 2026-08-30 19:06 (+0530) · Expand canonical document contract coverage

`5d443d9` · alwayss-snape

**Changed files**

- Tests: `M` tests/unit/test_resume_document.py

---

---

---

---

---

---

<!-- entry:2026-08-30T19:04:11+05:30 -->
## 2026-08-30 19:04 (+0530) · Test canonical resume document contract

`959be1a` · alwayss-snape

**Changed files**

- Tests: `A` tests/unit/test_resume_document.py

---

---

---

---

---

---

<!-- entry:2026-08-30T19:03:57+05:30 -->
## 2026-08-30 19:03 (+0530) · Add canonical versioned resume document model

`62a9751` · alwayss-snape

**Why / details** _(from the retired CHANGELOG.md / MEMORY.md)_

> V2 redesign Phase 1: `ResumeDocument` is a versioned JSON source of truth holding resume content, presentation preferences, import metadata and an auditable revision history. Every import, user edit or AI change can be recorded with its actor, changed paths and source evidence.

**Changed files**

- Domain models: `A` app/domain/resume_document.py

**Structure delta**

- new module `app/domain/resume_document.py`: `class ResumeDocument`, `class ResumePresentation`, `class ResumeRevision`, `class ResumeSource`

---

---

---

---

---

---

<!-- entry:2026-08-29T21:20:23+05:30 -->
## 2026-08-29 21:20 (+0530) · Keep grounded validation test deterministic

`965792f` · alwayss-snape

**Changed files**

- Tests: `M` tests/unit/test_validation.py

---

---

---

---

---

---

<!-- entry:2026-08-29T21:20:12+05:30 -->
## 2026-08-29 21:20 (+0530) · Allow grammatical variants in claim validation

`1adf729` · alwayss-snape

**Changed files**

- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/validation/factual.py`: added `FactualValidator._canonical_term()`

---

---

---

---

---

---

<!-- entry:2026-08-29T21:20:01+05:30 -->
## 2026-08-29 21:20 (+0530) · Test rejection of fabricated resume claims

`f5cfbee` · alwayss-snape

**Changed files**

- Tests: `M` tests/unit/test_validation.py

---

---

---

---

---

---

<!-- entry:2026-08-29T21:19:45+05:30 -->
## 2026-08-29 21:19 (+0530) · Cover conservative evidence matching

`c685f72` · alwayss-snape

**Changed files**

- Tests: `M` tests/unit/test_matcher.py

---

---

---

---

---

---

<!-- entry:2026-08-29T21:19:29+05:30 -->
## 2026-08-29 21:19 (+0530) · Preserve table-based DOCX resume layouts

`5460d07` · alwayss-snape

**Changed files**

- Rendering: `M` app/rendering/docx_patcher.py

**Structure delta**

- `app/rendering/docx_patcher.py`: added `DocxPatcher._replace_paragraph_text()`

---

---

---

---

---

---

<!-- entry:2026-08-29T21:19:08+05:30 -->
## 2026-08-29 21:19 (+0530) · Preview the rendered resume instead of plain Markdown

`729e2b4` · alwayss-snape

**Changed files**

- Entry points: `M` app/ui.py

---

---

---

---

---

---

<!-- entry:2026-08-29T21:18:54+05:30 -->
## 2026-08-29 21:18 (+0530) · Reject rewrites with unsupported claims

`c18b165` · alwayss-snape

**Changed files**

- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/validation/factual.py`: added `FactualValidator._factual_terms()`

---

---

---

---

---

---

<!-- entry:2026-08-29T21:18:31+05:30 -->
## 2026-08-29 21:18 (+0530) · Require cited evidence for alignment score credit

`4c7e776` · alwayss-snape

**Changed files**

- Analysis: `M` app/analysis/scoring.py

---

---

---

---

---

---

<!-- entry:2026-08-29T21:18:20+05:30 -->
## 2026-08-29 21:18 (+0530) · Ground JD requirements in verbatim source text

`507d156` · alwayss-snape

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py

**Structure delta**

- `app/analysis/jd_analyzer.py`: added `JDAnalyzer._category()`, `JDAnalyzer._is_requirement()`; removed `class LLMJDAnalysisOutput`

---

---

---

---

---

---

<!-- entry:2026-08-29T21:17:49+05:30 -->
## 2026-08-29 21:17 (+0530) · Harden evidence-only requirement matching

`209aa79` · alwayss-snape

**Changed files**

- Analysis: `M` app/analysis/matcher.py

**Structure delta**

- `app/analysis/matcher.py`: added `EvidenceMatcher._meaningful_tokens()`, `EvidenceMatcher._normalize_text()`; removed `EvidenceMatcher._normalize_term()`

---

---

---

---

---

---

<!-- entry:2026-08-29T21:09:09+05:30 -->
## 2026-08-29 21:09 (+0530) · fix: regex character class in skills normalizer

`dad4eff` · Kshitij Chaubey

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py

---

---

---

---

---

---

<!-- entry:2026-08-29T21:08:37+05:30 -->
## 2026-08-29 21:08 (+0530) · fix: resolve 0.0 alignment score bug & add live resume preview tab

`d87612d` · Kshitij Chaubey

**Why / details** _(from the retired CHANGELOG.md / MEMORY.md)_

> Root cause of the "0.0 / 100 alignment score": (1) `JDAnalyzer` only extracted requirements from lines starting with `-`, `•` or `*`, so JDs pasted as plain paragraphs gave zero requirements. (2) `ResumeNormalizer` treated every unbulleted PDF line under Experience as a new job header, leaving zero bullets and zero evidence. Both were fixed, token matching was loosened, and a "Live Preview" tab was added to the UI.

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py, `M` app/analysis/matcher.py, `M` app/analysis/resume_normalizer.py
- Entry points: `M` app/ui.py
- Services: `M` app/services/tailor.py

**Structure delta**

- `app/analysis/jd_analyzer.py`: added `JDAnalyzer.extract_keywords_from_text()`
- `app/analysis/matcher.py`: added `EvidenceMatcher._extract_key_tokens()`
- `app/services/tailor.py`: added `TailorService.generate_preview_md()`

---

---

---

---

---

---

<!-- entry:2026-08-29T20:57:48+05:30 -->
## 2026-08-29 20:57 (+0530) · feat: complete local resume tailor implementation (V1.0)

`db5f3aa` · Kshitij Chaubey

**Why / details** _(from the retired CHANGELOG.md / MEMORY.md)_

> V1.0 built in 15 phases: repo/env, local LLM harness (Ollama `qwen3:4b`), DOCX ingestion + DocumentMap, PDF ingestion + OCR path, resume normalization + evidence ledger, JD analysis, 3-layer matcher + weighted scoring, grounded tailoring planner, controlled rewriter, multi-layer validation gate, DOCX patcher + ATS template renderer, LibreOffice PDF + output QA, CLI + `TailorService`, Streamlit UI, and end-to-end tests.

**Changed files**

- Analysis: `A` app/analysis/jd_analyzer.py, `A` app/analysis/matcher.py, `A` app/analysis/resume_normalizer.py, `A` app/analysis/rewriter.py, `A` app/analysis/scoring.py, `A` app/analysis/tailor_planner.py
- Config: `A` app/config/settings.py
- Domain models: `A` app/domain/evidence.py, `A` app/domain/job.py, `A` app/domain/report.py, `A` app/domain/resume.py, `A` app/domain/tailoring.py
- Entry points: `A` app/cli.py, `A` app/ui.py
- Ingestion: `A` app/ingestion/docx.py, `A` app/ingestion/ocr.py, `A` app/ingestion/pdf.py
- LLM: `A` app/llm/client.py, `A` app/llm/prompts/final_review.txt, `A` app/llm/prompts/jd_analysis.txt, `A` app/llm/prompts/resume_normalization.txt, `A` app/llm/prompts/rewrite_bullet.txt, `A` app/llm/prompts/tailoring_plan.txt, `A` app/llm/prompts/validate_claims.txt, `A` app/llm/schemas.py
- Rendering: `A` app/rendering/document_map.py, `A` app/rendering/docx_patcher.py, `A` app/rendering/pdf_converter.py, `A` app/rendering/template_renderer.py
- Root: `A` .env.example, `A` .gitignore, `A` ARCHITECTURE.md, `A` BUILD.md, `A` CHANGELOG.md, `A` MEMORY.md, `A` README.md, `A` pyproject.toml
- Services: `A` app/services/run_manager.py, `A` app/services/tailor.py
- Tests: `A` tests/fixtures/jds/sample.txt, `A` tests/fixtures/resumes/sample.docx, `A` tests/fixtures/resumes/sample.pdf, `A` tests/integration/test_end_to_end.py, `A` tests/unit/test_cli.py, `A` tests/unit/test_docx_parser.py, `A` tests/unit/test_docx_renderer.py, `A` tests/unit/test_env.py, `A` tests/unit/test_jd_analyzer.py, `A` tests/unit/test_llm_client.py, `A` tests/unit/test_matcher.py, `A` tests/unit/test_pdf_converter.py, `A` tests/unit/test_pdf_parser.py, `A` tests/unit/test_resume_normalizer.py, `A` tests/unit/test_rewriter.py, `A` tests/unit/test_tailor_planner.py, `A` tests/unit/test_ui.py, `A` tests/unit/test_validation.py
- Tooling: `A` scripts/benchmark_model.py, `A` scripts/create_sample_docx.py, `A` scripts/create_sample_pdf.py
- Validation: `A` app/validation/factual.py, `A` app/validation/output.py, `A` app/validation/safety.py, `A` app/validation/structural.py

**Structure delta**

- new module `app/analysis/jd_analyzer.py`: `class JDAnalyzer`, `class LLMJDAnalysisOutput`
- new module `app/analysis/matcher.py`: `class EvidenceMatcher`
- new module `app/analysis/resume_normalizer.py`: `class ResumeNormalizer`
- new module `app/analysis/rewriter.py`: `class LLMRewriter`, `class RewriteProposal`
- new module `app/analysis/scoring.py`: `class AlignmentScorer`
- new module `app/analysis/tailor_planner.py`: `class TailoringPlanner`
- new module `app/cli.py`
- new module `app/config/settings.py`: `class Settings`
- new module `app/domain/evidence.py`: `class Evidence`
- new module `app/domain/job.py`: `class JobDescription`, `class Requirement`
- new module `app/domain/report.py`: `class Match`, `class TailoringReport`
- new module `app/domain/resume.py`: `class Candidate`, `class Education`, `class Experience`, `class Project`, `class Resume`, `class ResumeBullet`
- new module `app/domain/tailoring.py`: `class TailoringAction`, `class TailoringPlan`
- new module `app/ingestion/docx.py`: `class DocxParser`, `class RawBlock`, `class RawDocument`
- new module `app/ingestion/ocr.py`: `class OCREngine`
- new module `app/ingestion/pdf.py`: `class PdfParser`
- new module `app/llm/client.py`: `class LLMClient`
- new module `app/llm/schemas.py`: `class LLMConnectionError`, `class LLMError`, `class LLMInvalidJSONError`, `class LLMResponse`, `class LLMTimeoutError`
- new module `app/rendering/document_map.py`: `class DocumentLocation`, `class DocumentMap`
- new module `app/rendering/docx_patcher.py`: `class DocxPatcher`
- new module `app/rendering/pdf_converter.py`: `class PdfConverter`
- new module `app/rendering/template_renderer.py`: `class TemplateRenderer`
- new module `app/services/run_manager.py`: `class RunManager`
- new module `app/services/tailor.py`: `class TailorService`
- new module `app/ui.py`
- new module `app/validation/factual.py`: `class ClaimCheck`, `class FactualValidator`, `class ValidationResult`
- new module `app/validation/output.py`: `class OutputQAValidator`
- new module `app/validation/safety.py`: `class SafetyGuard`
- new module `app/validation/structural.py`: `class StructuralValidator`
- new module `scripts/benchmark_model.py`: `class SimpleResponse`
- new module `scripts/create_sample_docx.py`
- new module `scripts/create_sample_pdf.py`

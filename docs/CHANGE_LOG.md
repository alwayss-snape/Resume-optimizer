# Change Log — Resume-optimizer

Timestamped record of every **major** commit (anything touching `app/`, `scripts/`, `tests/`, `.githooks/` or
`pyproject.toml`), newest first. Entries are written automatically by the post-commit hook
(`scripts/update_docs.py log-entry`); docs-only commits and commits containing `[skip log]` are skipped.

- **Why** comes from the commit message body, so write one for anything non-trivial.
- **Structure delta** is computed from the code itself: classes and functions added or removed.
- You may hand-edit an entry to add context; the hook only rewrites an entry when that same commit is amended.

<!-- entries below; newest first -->

<!-- entry:2026-09-30T19:13:24+05:30 -->
## 2026-09-30 19:13 (+0530) · P1.14: Flag rewrites that drop information

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The validator blocked new facts and changed numbers, but a rewrite could
> still quietly lose information and PASS: in the real run a dashboard
> bullet lost the list of KPIs it tracked (F48). Tightening bullets to 28
> words (P1.4) makes this more likely, so the check has to exist before
> rewrites get more aggressive.
>
> FactualValidator.dropped_facts(original, rewritten) returns:
> - factual terms of the original (tools, acronyms, proper nouns, known
>   skills) missing from the rewrite;
> - the share of content words kept (connectors and generic verbs and
>   adjectives ignored; slashed terms like hours/month compared per part);
> - short list items (1-4 words between commas, "and", parentheses,
>   "including") that vanish entirely. The word share alone missed a lost
>   KPI list at 60% retention.
>
> Any dropped term, retention below 50%, or 2+ lost list items turns PASS
> into NEEDS_CONFIRM with "the rewrite drops ..." so the user decides;
> REJECT stays REJECT. Lowercase single letters are never facts ("a" had
> matched the JD keyword "A/B"). The rewrite prompt already lists what must
> be kept. Tests use invented bullets.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Tests: `M` tests/unit/test_validation.py
- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/validation/factual.py`: added `FactualValidator.dropped_facts()`

---

<!-- entry:2026-09-30T19:11:33+05:30 -->
## 2026-09-30 19:11 (+0530) · P1.3 + P1.4: Relevance planner and one rewrite call per role

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> After Stage B the real resume got 0 rewrites: the planner only picked
> bullets that matched a JD requirement (F13), and whole-line requirements
> rarely match a bullet. The rewriter made one call per bullet with the
> whole JD attached (F14), which hit the free tier's rate limits.
>
> P1.3 planner v2:
> - Relevance per bullet (0-1): half from weighted JD keywords the bullet
>   already contains (same lookup as the match rate), half from similarity
>   to its closest requirement (local embeddings, token overlap fallback),
>   +0.2 for a deterministic requirement match.
> - Every bullet with relevance >= 0.15 is rewritten; the rest are KEEP and
>   marked as trim candidates for page-fitting (P2.4).
> - Each action carries its top-3 requirements and allowed keywords: JD
>   keywords the bullet or its sub-heading already contains, so a rewrite
>   can't move a skill from one project to another.
> - plan.bullet_order puts the most relevant bullets first within each
>   sub-heading; applied when the template renders.
>
> P1.4 rewrite v2:
> - rewrite_role(): all of a job's REWRITE bullets in one structured call
>   (RoleRewriteResult). The prompt says to lead with the JD-relevant work,
>   use the requirement's wording only for work the bullet describes, keep
>   to 28 words, avoid repeated opening verbs, pronouns and buzzwords, and
>   keep every tool, number and specific detail.
> - Code guards: unknown or duplicate ids are ignored, keywords_used is
>   limited to allowed keywords present in the text, punctuation-only edits
>   count as unchanged, and a failed call marks each bullet llm_error with
>   the reason.
> - The first prompt version ("return it unchanged if strong") produced only
>   added full stops. The revised prompt produced real tightening
>   (25-28 -> 15-23 words) with all numbers and tools kept.
>
> Real resume x FOX JD: 10 of 12 bullets selected (was 0), rewrite step 1
> call (was 1 per bullet), 10/10 changed.

**Changed files**

- Analysis: `M` app/analysis/change_proposal.py, `M` app/analysis/rewriter.py, `M` app/analysis/tailor_planner.py
- Docs: `M` docs/ACTION_ITEMS.md
- Domain models: `M` app/domain/tailoring.py
- LLM: `A` app/llm/prompts/rewrite_role.txt, `M` app/llm/schemas.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_rewriter.py, `M` tests/unit/test_tailor_planner.py

**Structure delta**

- `app/analysis/rewriter.py`: added `LLMRewriter.rewrite_role()`, `_same_wording()`
- `app/analysis/tailor_planner.py`: added `TailoringPlanner._similarities()`, `_content()`, `_cosine()`
- `app/llm/schemas.py`: added `class RoleBulletRewrite`, `class RoleRewriteResult`
- `app/services/tailor.py`: added `TailorService._apply_bullet_order()`, `TailorService._embed()`

---

---

<!-- entry:2026-09-30T18:34:43+05:30 -->
## 2026-09-30 18:34 (+0530) · Load the embedding model from the local cache first

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Semantic matching was silently off: sentence-transformers is declared in
> pyproject.toml but wasn't installed in .venv_py311, so SemanticMatcher
> quietly skipped itself (the test suite dropped from ~80 s to ~20 s without
> anyone noticing). With it reinstalled, every model load did Hugging Face
> Hub update checks over the black-holed IPv6 route: 92 s per load, 6 min
> for the test suite.
>
> SentenceTransformer is now loaded with local_files_only=True first and
> falls back to an online load (first-time download) only if that fails.
> Model load: 92 s -> 9 s; test suite: 351 s -> 32 s. CLAUDE.md and the
> overview note the dependency and the new test time.

**Changed files**

- Analysis: `M` app/analysis/semantic_matcher.py
- Docs: `M` docs/PROJECT_OVERVIEW.md
- Root: `M` CLAUDE.md
- Tests: `M` tests/unit/test_semantic_matcher.py

---

---

---

<!-- entry:2026-09-30T18:17:09+05:30 -->
## 2026-09-30 18:17 (+0530) · P1.2: Keyword match rate as the headline score

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> After Stage A the old score read 0 on the real resume: it asked whether a
> whole JD sentence appears in one bullet, which never happens with
> whole-line requirements (F12). ATS systems and Jobscan score by keywords,
> so the headline score now does too, with a table that explains it.
>
> - analysis/keyword_match.py: one row per JD keyword (hard skills 3, title
>   2, education/certifications 1.5, soft skills 1; x1.5 when the keyword
>   appears in a required line) with found / where / JD count; rate is the
>   weighted share found. Matching is alias-aware, plural-insensitive and
>   whole-token (R is not React, ML is not MLflow), handles implied terms
>   (PySpark -> Spark), and accepts multi-word terms spread across one
>   sentence. The job title gets partial credit from role titles and the
>   headline.
> - The rate is the headline in analyze_only, generate_proposals and
>   before/after tailor_resume; the requirement-level score stays as
>   evidence_score. changes.md gets a keyword table; the UI shows the rate
>   against the 75-85% band and a matched/missing table in analysis,
>   proposal review and results.
> - tailor_resume(job_desc=...) reuses the proposal-time JD analysis (UI and
>   harness pass it). A second analysis cost a call and returned a slightly
>   different keyword list, so the before/after rates disagreed (30.8 ->
>   24.1 with no changes applied).
> - Harness: match.score is the rate; with --tailor it uses the pipeline's
>   own JD analysis.
>
> Real resume x FOX JD (live): 0.0 -> 29.3% with 8 matched keywords; 6 calls
> (was 8), 10.5K tokens (was 20.6K). Offline baseline re-recorded.

**Changed files**

- Analysis: `A` app/analysis/keyword_match.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Domain models: `M` app/domain/report.py
- Entry points: `M` app/ui.py
- Root: `M` app/eval/harness.py, `M` data/eval/baseline.json
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_eval_harness.py, `A` tests/unit/test_keyword_match.py, `M` tests/unit/test_tailor_resume_flow.py
- Tooling: `M` scripts/update_docs.py

**Structure delta**

- new module `app/analysis/keyword_match.py`: `class KeywordMatcher`
- `app/domain/report.py`: added `KeywordMatchReport.matched()`, `KeywordMatchReport.missing()`, `class KeywordMatchReport`, `class KeywordRow`
- `app/ui.py`: added `_show_keyword_match()`

---

---

---

---

<!-- entry:2026-09-30T18:07:42+05:30 -->
## 2026-09-30 18:07 (+0530) · P4.1: Evaluation harness with offline and live baselines

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Stage B starts with measurement: every later change has to show
> improvement against a recorded baseline rather than an eyeballed run.
>
> - python -m app.eval run [--live] [--tailor] [--case] [--compare] [--save]
> - Cases: data/eval/cases.json (anonymized replica PDF, sample DOCX,
>   sample PDF), plus data/eval/private/cases.json (the user's resume x FOX
>   JD), which is gitignored and skipped when absent.
> - Deterministic metrics: golden-parse match, parse stats, JD stats, score
>   and match statuses, and JD keyword coverage (a plain whole-term measure
>   that doesn't depend on the matcher). --tailor adds proposals, verdicts,
>   suggestions, score after and page count; live runs add LLM calls,
>   tokens, seconds and 429 retries.
> - Offline mode uses a stub LLM that reports "unavailable", so every
>   component takes its deterministic path and the numbers are reproducible.
> - compare() prints per-metric deltas and flags regressions (for example
>   more calls or pages).
> - --save drops private cases from any file outside data/eval/private.
> - The golden-file projection moved into app/eval/golden.py.
>
> Baselines recorded: data/eval/baseline.json (offline, committed cases)
> and a private live baseline for the real case: score 0.0, 7/28 keywords
> verbatim, 0 rewrites, 8 calls, 20.6K tokens, 4 x 429, 2 pages.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Root: `A` app/eval/__init__.py, `A` app/eval/__main__.py, `A` app/eval/golden.py, `A` app/eval/harness.py, `A` data/eval/baseline.json, `A` data/eval/cases.json
- Tests: `M` tests/integration/test_parse_golden.py, `A` tests/unit/test_eval_harness.py
- Tooling: `M` scripts/update_docs.py

**Structure delta**

- new module `app/eval/__init__.py`
- new module `app/eval/__main__.py`
- new module `app/eval/golden.py`
- new module `app/eval/harness.py`: `class Case`, `class OfflineLLM`, `class _RetryCounter`

---

---

---

---

---

<!-- entry:2026-09-30T17:50:19+05:30 -->
## 2026-09-30 17:50 (+0530) · P3.5: "Check parsed resume" step before tailoring

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The real-resume run produced unusable output because the parse was wrong,
> and nothing showed the parse to the user before rewriting started. Parsing
> is now much better (P1.11-P1.13), but no parser is perfect, so the user
> gets one look before the LLM spends calls on a misread resume.
>
> - "Tailor & Generate" now parses first and shows a check form: parse
>   problems from StructureExtractor as warnings; editable name, headline,
>   email, phone, location, links; per job company, location and each
>   role's title and dates. Bullets are reviewed in the next step, as before.
> - TailorService.apply_parse_corrections() applies the edits to a deep
>   copy, never touches bullet text, keeps experience evidence in step with
>   a renamed company, and records a user revision.
> - generate_proposals() and tailor_resume() accept the checked parse
>   (parsed=...), so Apply & Generate no longer re-parses the file. That
>   means no second structure-extraction call, and corrections carry
>   through. Corrections can't be patched into the original DOCX, so they
>   switch PRESERVE output to the ATS template.
> - Covered by service tests and a Streamlit AppTest of the new stage. The
>   AppTest uses a temp copy of the fixture, because the UI's "Start Over"
>   deletes the uploaded file.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/ui.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_check_parsed_resume.py

**Structure delta**

- `app/services/tailor.py`: added `TailorService._copy_parsed()`, `TailorService.apply_parse_corrections()`
- `app/ui.py`: added `_draft_proposals()`

---

---

---

---

---

---

<!-- entry:2026-09-30T17:46:47+05:30 -->
## 2026-09-30 17:46 (+0530) · P1.1: JD analysis v2 (one structured call, verbatim guard, whole-line requirements)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> On the real run the JD analysis was the second input failure: no title or
> company (the FOX JD has no "Job Title:" label), junk requirements from
> splitting on "and" ("Design", "Mentor"), "Nice To Have, But Not Required"
> items marked required, and keywords like WHAT / WILL / FOX / Corporation.
>
> - One JDAnalysisResult call over all numbered lines replaces the
>   line-selection call (still one call): title, company, seniority,
>   min/max years, requirement lines by index with priority and category,
>   hard/soft skills, education, certifications.
> - Verbatim guard: every string must be found in the JD (the JD's own
>   spelling is kept); years must appear in the text. Otherwise the
>   deterministic value stands, so the model can classify but not invent.
> - Requirements are whole lines (no "and"-splitting) with source spans.
> - Deterministic fallback also improved: title/company from "X is looking
>   for a <title> to join", seniority from the title, years regex, headings
>   by known patterns / ALL CAPS / short known-section lines, a
>   "Nice To Have, But Not Required" section => preferred, intro prose
>   skipped.
> - Keywords = verified hard skills + certifications, topped up with
>   technical terms from the requirement lines only (gpt-oss varies between
>   runs; the intro holds team names and title codes), ranked by a
>   frequency count done in code (keyword_counts).
>
> FOX JD live: 1 call, ~5K tokens, ~6 s. Title, company, senior, 3-7 years
> right; 21-22 whole-line requirements, 4 preferred. Tests use an anonymized
> JD with the same traits.

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Domain models: `M` app/domain/job.py
- LLM: `M` app/llm/prompts/jd_analysis.txt, `M` app/llm/schemas.py
- Tests: `A` tests/fixtures/jds/replica_layout_jd.txt, `M` tests/unit/test_jd_analyzer_llm.py, `A` tests/unit/test_jd_analyzer_v2.py

**Structure delta**

- `app/analysis/jd_analyzer.py`: added `JDAnalyzer._clean_line()`, `JDAnalyzer._contains_term()`, `JDAnalyzer._heuristic_title_company()`, `JDAnalyzer._is_heading()`, `JDAnalyzer._llm_analyze()`, `JDAnalyzer._seniority()`, `JDAnalyzer._verbatim()`, `JDAnalyzer._verbatim_list()`, `JDAnalyzer._years()`, `JDAnalyzer.count_occurrences()`; removed `JDAnalyzer._llm_select_requirement_lines()`, `JDAnalyzer._segment_line()`
- `app/llm/schemas.py`: added `class JDAnalysisResult`, `class JDRequirementLine`; removed `class JDRequirementSelection`

---

---

---

---

---

---

---

<!-- entry:2026-09-30T17:41:04+05:30 -->
## 2026-09-30 17:41 (+0530) · P1.9: Parse links and headline; walk DOCX in document order

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> LinkedIn/GitHub links never reached the output, a headline under the name
> had nowhere to go, and DOCX tables were read after every paragraph, so a
> job header laid out as a table landed under whichever section came last.
>
> - Links come from DOCX hyperlink relationships, PDF link annotations and
>   URLs written in the header. They're deduped, mailto:/tel: are dropped
>   (mailto fills a missing email), and they render short
>   ("linkedin.com/in/x").
> - Candidate.headline: a short line under the name that isn't contact
>   info, a location, a sentence or a "LinkedIn | Email" placeholder.
>   Rendered in DOCX, HTML and the preview; stored as summary evidence.
> - DOCX: paragraphs and tables walked in document order
>   (iter_inner_content), merged cells read once, cell paragraphs
>   classified like body paragraphs, Word page-header contact details read.
> - A short plain line directly above a dated line is a company (plain,
>   non-bold company lines were becoming bullets of an empty job).
> - Short header lines (name/contact/headline/links) are no longer "stray"
>   evidence, so they don't trigger the P1.13 LLM fallback.
>
> Placeholder company/title and the "Previously:" note were already
> removed by P1.12.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Domain models: `M` app/domain/resume.py
- Ingestion: `M` app/ingestion/docx.py
- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/template_renderer.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_parsing_fixes_p19.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._header_urls()`, `ResumeNormalizer._is_headline()`, `ResumeNormalizer._merge_links()`
- `app/domain/resume.py`: added `Candidate.display_links()`
- `app/ingestion/docx.py`: added `DocxParser._classify()`, `DocxParser._hyperlinks()`

---

---

---

---

---

---

---

---

<!-- entry:2026-09-30T17:36:31+05:30 -->
## 2026-09-30 17:36 (+0530) · Connect to Groq over IPv4: each call was stalling ~150 s

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A live check during P1.13 took 151 s for one ~1K-token call, and
> check-llm took 150.8 s where the baseline was 0.7 s. A raw curl request
> took 0.7 s. The cause: api.groq.com resolves to IPv6 addresses first,
> IPv6 is black-holed on this network, and httpx (unlike curl) has no
> "happy eyeballs", so it waits out each IPv6 address (~75 s) before it
> falls back to IPv4. At 8-19 calls per run that is 20-45 minutes of waiting
> that looked like a slow model, and it would distort every Stage B-C
> latency number.
>
> The Groq provider now uses one httpx.Client bound to IPv4
> (local_address="0.0.0.0"), which also reuses the connection across calls.
> The new setting GROQ_FORCE_IPV4 defaults to true; Groq's Cloudflare
> endpoint always serves IPv4. check-llm: 150.8 s -> 0.7 s. [P0.5 follow-up]

**Changed files**

- Config: `M` app/config/settings.py
- LLM: `M` app/llm/client.py
- Root: `M` .env.example
- Tests: `M` tests/unit/test_llm_client.py

---

---

---

---

---

---

---

---

---

<!-- entry:2026-09-30T17:35:31+05:30 -->
## 2026-09-30 17:35 (+0530) · P1.13: LLM-assisted structure extraction with a verbatim guard

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Rules can't cover every resume layout. When the deterministic parse looks
> wrong, the LLM now labels the file's numbered lines by index (name, section
> heading, company, job title, sub-heading, bullet, text), the same pattern
> as JD line selection. It never returns text, so every value in the resume
> is still copied verbatim from the file.
>
> - StructureExtractor.problems(): no or odd name, bullets but no jobs, a job
>   without company/title/bullets, 3+ lines outside any known section.
>   A clean parse (the user's resume, the replica) makes no LLM call.
> - Labels become RawBlock.hint on a copy of the raw document; the normalizer
>   honours hints over its layout guesses and re-runs. The re-parse is kept
>   only if it has fewer problems. Hallucinated / duplicate indices are
>   dropped.
> - TailorService.parse_resume()/normalize_raw() replace three copies of
>   parse+normalize; remaining problems are exposed as last_parse_issues and
>   in generate_proposals()["parse_issues"] for the P3.5 review step.
> - Date ranges accept "to" ("2019 to 2023"), and only a month name may
>   precede the year: "Senior Engineer 2019 - 2023" used to lose "Engineer".
>
> Live Groq check on an odd layout: 1 call, ~1K tokens, all problems fixed.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py, `A` app/analysis/structure_extractor.py
- Docs: `M` docs/ACTION_ITEMS.md
- Ingestion: `M` app/ingestion/docx.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_resume_model_v2.py, `A` tests/unit/test_structure_extractor.py
- Tooling: `M` scripts/update_docs.py

**Structure delta**

- new module `app/analysis/structure_extractor.py`: `class LineLabel`, `class ResumeLineLabels`, `class StructureExtractor`
- `app/services/tailor.py`: added `TailorService.normalize_raw()`, `TailorService.parse_resume()`

---

---

---

---

---

---

---

---

---

---

<!-- entry:2026-09-30T17:20:52+05:30 -->
## 2026-09-30 17:20 (+0530) · P1.12: Resume model v2 (several roles per company, project sub-sections in a job)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The user's resume lists one company with two roles (a promotion) and four
> project sub-sections, each with its own bullets. The old model had one
> title per Experience, so the normalizer invented a "Professional
> Experience" company, turned project headings into bullets or fake jobs, and
> recorded the earlier role as a synthetic "Previously:" bullet.
>
> - domain: Role model; Experience.roles (most recent first; title/dates
>   still mirror the latest role so existing callers keep working);
>   ResumeBullet.group holds the sub-heading a bullet sits under. Keeping
>   bullets flat on the Experience means the planner, rewriter and apply
>   step (which walk exp.bullets) need no change.
> - normalizer: a heading-like line followed by a dated line is a company;
>   otherwise it's a sub-heading. Title-before-company order is handled, a
>   new title after bullets stays at the same company, and unknown
>   company/title are left empty instead of placeholders.
> - DATE_PATTERN matched any word starting with a month abbreviation
>   ("Market", "Decision", "Junior"), which made "Market Basket Analysis
>   Framework" a job line. Months are now whole words, and a job line needs
>   a year or "Present".
> - DOCX template, HTML and the markdown preview render extra roles and
>   sub-headings, and skip empty company/title.
> - Golden-file test: the committed replica and (locally only) the user's
>   real resume both match their hand-checked golden parse.
> - Import PyMuPDF as `pymupdf`; the `fitz` alias prints a deprecation
>   warning to stdout, which corrupted JSON printed by scripts.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Domain models: `M` app/domain/resume.py
- Entry points: `M` app/ui.py
- Ingestion: `M` app/ingestion/pdf.py
- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/template_renderer.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/fixtures/resumes/make_replica_layout_pdf.py, `A` tests/fixtures/resumes/replica_layout.golden.json, `A` tests/integration/test_parse_golden.py, `A` tests/unit/test_resume_model_v2.py
- Validation: `M` app/validation/output.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._add_role()`, `ResumeNormalizer._experience_line_kind()`, `ResumeNormalizer._is_dated_line()`
- `app/domain/resume.py`: added `Experience.all_roles()`, `Experience.bullet_groups()`, `class Role`
- `app/rendering/html_renderer.py`: added `HtmlResumeRenderer._dates()`, `HtmlResumeRenderer._experience_entry()`
- `app/rendering/template_renderer.py`: added `TemplateRenderer._role_dates()`

---

---

---

---

---

---

---

---

---

---

---

<!-- entry:2026-09-30T17:15:47+05:30 -->
## 2026-09-30 17:15 (+0530) · P1.11: Layout-aware PDF parsing (name by font size, bullets by indent, right columns)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The real-resume run showed the PDF parser, not the rewriter, was the main
> problem: the old code split PyMuPDF "blocks" into text lines and guessed
> structure from the text alone. The name was taken from a project heading,
> wrapped bullet lines that started with a capital or were set in bold became
> separate bullets, "●" + zero-width spaces leaked into bullets, right-aligned
> locations and dates landed in the wrong field, and a two-category skills
> line was read as one category.
>
> The parser now reads get_text("dict"), which keeps font size, bold and x/y
> for every line:
> - name = largest text on page 1 when clearly larger than body text
>   (emitted as a "name" block; flat PDFs fall back to the old heuristic)
> - bullet continuations are joined by indentation, paragraphs when a line
>   runs to the right margin; the lowercase rule stays as a fallback; never
>   join across a font-size jump or onto a "Label:" line
> - a short right-aligned run on the same row, or a 3+ space gap, becomes a
>   tab, which the normalizer already reads as the right-hand column
> - headings are found by known names or uppercase + bold/body size, even
>   with leading spaces
> - invisible characters, NBSP and soft hyphens are cleaned
>
> The normalizer splits "Languages: … Frameworks: …" lines into categories,
> drops a leading "and" from the last list item, and lets a line's own label
> ("Certifications:", "Interests:") decide its bucket in mixed sections.
>
> Tests use an anonymized replica PDF with the same layout traits, created
> by a committed generator script. Roles and project sub-sections inside a
> job still need the model change in P1.12.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Ingestion: `M` app/ingestion/docx.py, `M` app/ingestion/pdf.py
- Tests: `A` tests/fixtures/resumes/make_replica_layout_pdf.py, `A` tests/fixtures/resumes/replica_layout.pdf, `M` tests/unit/test_pdf_parser.py, `M` tests/unit/test_resume_normalizer.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._skill_items()`, `ResumeNormalizer._split_skill_line()`
- `app/ingestion/pdf.py`: added `PdfParser._assemble()`, `PdfParser._attach_right_columns()`, `PdfParser._body_size()`, `PdfParser._continues()`, `PdfParser._is_heading()`, `PdfParser._page_lines()`, `PdfParser._split_bullet()`, `_clean()`, `_is_bold_span()`, `class _Line`

---

---

---

---

---

---

---

---

---

---

---

---

<!-- entry:2026-09-30T16:50:02+05:30 -->
## 2026-09-30 16:50 (+0530) · P1.8: Rebalance fact validator (PASS / NEEDS_CONFIRM / REJECT); keep user edits

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The validator treated every new word as an unsupported fact, so ordinary
> rewording ("cutting", "processed", "implemented") was rejected. In the first
> live Groq run, 0 of 2 good rewrites survived. It now separates ordinary
> English (allowed to change) from factual-looking terms: tools, acronyms,
> proper nouns, JD skills and scope claims such as "led a team" or
> "mentored". A factual term must come from the bullet's own source (PASS);
> if it's only elsewhere in the resume the rewrite is kept but flagged
> (NEEDS_CONFIRM); if it's nowhere, or any number changed, it's REJECT.
> Matching is inflection- and alias-aware (cutting/cut, k8s/Kubernetes).
>
> Proposals are fact-checked when generated, so the review UI shows each
> verdict before Apply. Text the user edits in the review form is kept as
> user-attested and noted in the report, instead of being silently dropped
> (F17). Same live run: 2 of 2 rewrites now survive; Terraform, "Led a
> team" and 35%->40% are still rejected.

**Changed files**

- Analysis: `M` app/analysis/change_proposal.py
- Docs: `M` docs/ACTION_ITEMS.md
- Entry points: `M` app/ui.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_tailor_resume_flow.py, `M` tests/unit/test_validation.py
- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/validation/factual.py`: added `FactualValidator.__init__()`, `FactualValidator._is_factual()`, `FactualValidator._keys()`, `FactualValidator._stem()`, `FactualValidator._term_keys()`; removed `FactualValidator._canonical_term()`, `FactualValidator._factual_terms()`

---

---

---

---

---

---

---

---

---

---

---

---

---

<!-- entry:2026-09-30T16:45:06+05:30 -->
## 2026-09-30 16:45 (+0530) · Normalize typographic Unicode in LLM output; keep metrics verbatim

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Found in the first live Groq run: gpt-oss writes non-breaking hyphens and
> narrow no-break spaces ("high‑throughput", "50 M"), which look identical
> but break the number check, keyword matching and ATS parsing. Rewrites and
> suggestions are now normalised to ASCII spaces/hyphens, and a number split
> from its unit is rejoined. The rewrite prompt also asks for metrics to be
> copied verbatim (it had turned "50M+" into "over 50 M").
>
> Records the decision to use the Groq free tier only; the Claude provider
> stays in the code but is shelved.

**Changed files**

- Analysis: `M` app/analysis/rewriter.py
- Docs: `M` docs/ACTION_ITEMS.md
- LLM: `M` app/llm/prompts/rewrite_bullet.txt
- Tests: `M` tests/unit/test_rewriter.py

**Structure delta**

- `app/analysis/rewriter.py`: added `normalize_llm_text()`

---

---

---

---

---

---

---

---

---

---

---

---

---

---

<!-- entry:2026-09-30T16:39:23+05:30 -->
## 2026-09-30 16:39 (+0530) · P0.10: Add check-llm command for a live provider/model smoke test

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> One structured call to the configured (or overridden) provider; prints provider, model, latency and tokens, or the exact reason it's unavailable. Exit code 0/1 so it can gate scripts.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Entry points: `M` app/cli.py
- Tests: `M` tests/unit/test_cli.py

**Structure delta**

- `app/cli.py`: added `check_llm()`

---

---

---

---

---

---

---

---

---

---

---

---

---

---

---

<!-- entry:2026-09-30T16:38:31+05:30 -->
## 2026-09-30 16:38 (+0530) · P0.2 + P0.4: Provider-aware model picker; make rewrite failures visible

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> P0.2: the sidebar offered only Ollama model names and passed the choice to
> LLMClient regardless of provider, so with LLM_PROVIDER=groq every call
> asked Groq for "qwen3:4b". It now shows the configured provider and only
> that provider's models, with the configured default first.
>
> P0.4: rewrite failures were indistinguishable from "no change needed":
> the original text came back as the proposal with no explanation. Each
> proposal now carries a status (ok / unchanged / llm_unavailable /
> llm_error) and error; generate_proposals returns an llm_status summary,
> and the UI shows "N of M rewrites failed: <reason>" plus a per-bullet note.
> The proposal stage's LLM usage (most of the calls) is now merged into the
> run's llm_usage.json instead of being lost.

**Changed files**

- Analysis: `M` app/analysis/change_proposal.py, `M` app/analysis/rewriter.py
- Docs: `M` docs/ACTION_ITEMS.md
- Entry points: `M` app/ui.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_rewriter.py, `M` tests/unit/test_tailor_resume_flow.py

**Structure delta**

- `app/analysis/rewriter.py`: added `LLMRewriter.rewrite_bullet_with_status()`
- `app/services/tailor.py`: added `_merge_usage()`
- `app/ui.py`: added `model_options()`

---

---

---

---

---

---

---

---

---

---

---

---

---

---

---

---

<!-- entry:2026-09-30T16:36:34+05:30 -->
## 2026-09-30 16:36 (+0530) · P0.1 + P0.3 + P0.5: Add Claude provider; model-aware cached health check; Groq 429 retry

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> P0.1: LLM_PROVIDER=anthropic uses the official anthropic SDK (default
> claude-opus-5-5). generate_json uses structured outputs (beta.messages.parse
> with the Pydantic model as output_format), so JSON matches the schema by
> construction: no schema-in-prompt, no parse-retry loop. Effort is passed via
> output_config (JD line selection uses "low"); no temperature (rejected by
> current Claude models); refusal and max_tokens stop reasons raise LLMError;
> server-side refusal fallback is enabled. System messages are lifted to the
> top-level system field.
>
> P0.3: is_available() is cached per client instance (one check per run
> instead of an HTTP round-trip before every call) and verifies the model
> actually exists: the Groq check previously accepted any HTTP 200, so the
> UI's Ollama model name ("qwen3:4b") passed the check and then every call
> failed silently. last_error records why a provider is unavailable.
>
> P0.5: Groq 429s are retried honouring retry-after (capped, 3 retries);
> gpt-oss models use strict json_schema output and reasoning_effort.

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py
- Config: `M` app/config/settings.py
- Docs: `M` docs/ACTION_ITEMS.md
- LLM: `M` app/llm/client.py
- Root: `M` .env.example, `M` ARCHITECTURE.md, `M` pyproject.toml
- Tests: `M` tests/unit/test_llm_client.py

**Structure delta**

- `app/llm/client.py`: added `LLMClient._anthropic_check()`, `LLMClient._anthropic_request()`, `LLMClient._anthropic_response()`, `LLMClient._check_available()`, `LLMClient._generate_anthropic()`, `LLMClient._generate_json_anthropic()`, `LLMClient._groq_check()`, `LLMClient._groq_supports_strict_schema()`, `LLMClient._ollama_check()`, `LLMClient._record()`, `LLMClient._split_system()`, `_retry_after_seconds()`, `strict_json_schema()`; removed `LLMClient._groq_is_available()`

---

---

---

---

---

---

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

---

---

---

---

---

---

---

---

---

---

---

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

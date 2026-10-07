# Change Log — Resume-optimizer

Timestamped record of every **major** commit (anything touching `app/`, `scripts/`, ` tests/`, `.githooks/` or
`pyproject.toml`), newest first. Entries are written automatically by the post-commit hook
(`scripts/update_docs.py log-entry`); docs-only commits and commits containing `[skip log]` are skipped.

- **Why** comes from the commit message body, so write one for anything non-trivial.
- **Structure delta** is computed from the code itself: classes and functions added or removed.
- You may hand-edit an entry to add context; the hook only rewrites an entry when that same commit is amended.

<!-- entries below; newest first -->

<!-- entry:2026-10-07T21:41:49+05:30 -->
## 2026-10-07 21:41 (+0530) · P10.3: region suggested from the JD sets paper and dates, switchable in Arrange

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> US employers expect Letter paper and 01/2022 dates; the template only did A4
> and "Jan 2022". The owner's decision: suggest the region from the JD,
> let the user confirm or change it, and only advise on personal details.
>
> analysis/region.py reads the JD deterministically (USAJOBS / GS grades,
> Indian cities, "City, ST", country and city names, currency) and keeps the
> matched words as evidence. apply_region sets page_size (P10.2) and a new
> date_style; numeric dates are derived from the usual formatting, so years,
> "Present" and "Expected" stay as they were. Review shows the suggestion
> with its evidence as a select; Arrange switches it with no LLM call. For
> US / UK / EU jobs, content checks point out a date of birth, father's name,
> declaration and the like, without removing anything. The CLI and eval
> pass no region, so their output is unchanged (eval 50 pass / 2 xfail).

**Changed files**

- Analysis: `A` app/analysis/region.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Domain models: `M` app/domain/resume_document.py
- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/layout.py, `M` app/rendering/template_renderer.py
- Root: `A` web/src/components/RegionChoice.test.tsx, `A` web/src/components/RegionChoice.tsx, `M` web/src/lib/api.ts, `M` web/src/lib/arrange.ts, `M` web/src/lib/review.test.ts, `M` web/src/lib/review.ts, `M` web/src/lib/types.ts, `M` web/src/pages/Arrange.test.tsx, `M` web/src/pages/Arrange.tsx, `M` web/src/pages/Review.tsx
- Services: `M` app/services/arrange.py, `M` app/services/tailor.py
- Tests: `A` tests/unit/test_region_p103.py
- Tooling: `M` scripts/update_docs.py
- Validation: `M` app/validation/content_lint.py
- Web API: `M` app/api/routes.py

**Structure delta**

- new module `app/analysis/region.py`: `class RegionGuess`
- `app/api/routes.py`: added `_region_out()`
- `app/rendering/layout.py`: added `numeric_dates()`

---

<!-- entry:2026-10-07T21:28:37+05:30 -->
## 2026-10-07 21:28 (+0530) · P10.2: one PageSpec for A4 and US Letter across DOCX, HTML and page-fit

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A4 was hard-coded in the DOCX template, the HTML preview's @page and width,
> and page-fit's body height and bullet line length. US jobs (P10.3) need
> Letter, and the three must agree or page-fit trims for the wrong page.
>
> PageSpec (rendering/layout.py) holds the paper size, its CSS size and the
> characters of a 10.5pt bullet per line; ResumePresentation.page_size picks
> it. Letter's line length was measured on rendered PDFs (98 vs 94 chars a
> line for the same bullets), so 96 against A4's 92. A4 output is unchanged:
> same twips in the DOCX, same CSS.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Domain models: `M` app/domain/resume_document.py
- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/layout.py, `M` app/rendering/page_fit.py, `M` app/rendering/template_renderer.py
- Tests: `A` tests/unit/test_page_size_p102.py

**Structure delta**

- `app/rendering/layout.py`: added `PageSpec.body_pt()`, `PageSpec.height_pt()`, `class PageSpec`, `page_spec()`

---

<!-- entry:2026-10-07T03:09:02+05:30 -->
## 2026-10-07 03:09 (+0530) · P10.11: Check details shows how a file was read as a note, not a problem

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The Stage O walkthrough showed the LinkedIn note under "Possible reading
> problem:", and a LinkedIn role with no description as "If it isn't a
> job, remove it". Neither is a problem: the note is information, and a role
> without a description is normal in an export, so that advice nudges people
> to delete a real job.
>
> /api/parse now returns parse_notes apart from parse_issues. Check details
> shows notes in a plain box with an info icon. For a layout-read file,
> "experience without bullets" is no longer a reading problem; Results'
> content checks still suggest bullets for it.
>
> The walkthrough script also takes RESUME / JD_FILE, so the gate could
> walk the LinkedIn export through every screen.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Root: `M` web/src/App.test.tsx, `M` web/src/App.tsx, `M` web/src/components/Icon.tsx, `M` web/src/lib/store.ts, `M` web/src/lib/types.ts, `M` web/src/pages/Details.tsx
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_linkedin_import_p101.py
- Tooling: `M` scripts/walkthrough.cjs
- Web API: `M` app/api/routes.py

---

<!-- entry:2026-10-07T02:46:16+05:30 -->
## 2026-10-07 02:46 (+0530) · P10.10: retry a long role in two halves when Groq runs out of tokens

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The Stage O private live run lost 10 of 12 bullets in 2 of 3 runs on
> 2026-10-07. Captured error: Groq json_validate_failed, "max completion
> tokens reached before generating a valid document", on the 10-bullet role
> call, on every try, even after effort dropped to low. The free tier caps a
> completion to what fits its 8K tokens-per-minute budget next to the
> prompt, so a long role's answer can simply not fit.
>
> When a role call of 4+ bullets fails that way, it is now retried as two
> half-size calls, each needing half the output. Normal runs make exactly
> the same calls as before; the follow-up for skipped bullets still runs.

**Changed files**

- Analysis: `M` app/analysis/rewriter.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Tests: `M` tests/unit/test_rewriter.py

---

<!-- entry:2026-10-07T02:36:16+05:30 -->
## 2026-10-07 02:36 (+0530) · P10.1: read a LinkedIn "Save to PDF" export by its two-column layout

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A LinkedIn profile export interleaved its sidebar and main column when read
> line by line: no email, phone or place, companies read as bullets and
> roles as sub-headings. The export's layout is fixed, so a dedicated reader
> (app/ingestion/linkedin.py) takes it apart deterministically: the two
> columns separately, "Page N of M" footers and LinkedIn's durations
> dropped, and every block hinted (name, headline, location, company,
> job_title, bullet, section:X) so the normalizer guesses nothing. Text is
> copied from the file; only date separators are rewritten.
>
> Detection is strict (name right of 25% of the width, no line crossing the
> column gap, sidebar under 38%, a known sidebar heading, a footer or
> profile URL), and the reader returns None whenever a line doesn't fit the
> pattern, so the normal parse still runs for everything else. The replica
> and private golden parses are unchanged.
>
> The normalizer gained headline / location hints ("Pune, Maharashtra,
> India" has three parts, which the contact-line rule never takes for a
> place). The service skips the LLM re-label for a layout-read file, since
> a role with no description is normal in an export and re-labelling would
> spend Groq tokens for nothing, and adds a note on Check details.
>
> Built fixture-first: an anonymized generator and a hand-written golden
> file, then the parser, which matched it.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Ingestion: `M` app/ingestion/docx.py, `A` app/ingestion/linkedin.py, `M` app/ingestion/pdf.py
- Root: `M` data/eval/cases.json
- Services: `M` app/services/tailor.py
- Tests: `A` tests/fixtures/resumes/linkedin_export.golden.json, `A` tests/fixtures/resumes/linkedin_export.pdf, `A` tests/fixtures/resumes/make_linkedin_export_pdf.py, `M` tests/integration/test_parse_golden.py, `M` tests/unit/test_eval_harness.py, `A` tests/unit/test_linkedin_import_p101.py
- Tooling: `M` scripts/update_docs.py

**Structure delta**

- new module `app/ingestion/linkedin.py`: `class _Reader`
- `app/ingestion/pdf.py`: added `PdfParser._raw_page_lines()`; removed `PdfParser._page_lines()`

---

<!-- entry:2026-10-06T08:15:25+05:30 -->
## 2026-10-06 08:15 (+0530) · P9.25: verbatim headings keep small words in lower case

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The live academic persona run (P9.10) printed "GRANTS AND FUNDING" as
> "Grants And Funding". Headings kept verbatim (P8.3) were title-cased with
> str.title(), which capitalises every word and also the letter after an
> apostrophe ("Dean'S List"). _display_heading now capitalises word by word,
> keeps short connector words lower case after the first word, and handles a
> non-ASCII first letter. Mixed-case headings are still kept as written.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Tests: `M` tests/unit/test_kept_sections_p83.py

---

<!-- entry:2026-10-06T08:14:47+05:30 -->
## 2026-10-06 08:14 (+0530) · P9.24: a current job's present-tense bullets stay in the present tense

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The live academic persona run (P9.10) rewrote "Lead a lab of 4 PhD
> students" as "Led ..." and "Teach BIO 210" as "Taught ..." in a job held
> since 2019. The role prompt only gave the model the company and titles and
> asks for a past-tense opening verb, so it had no way to know the job was
> ongoing. The prompt now carries each title's dates and says when the job is
> current, and keep_present_tense restores the bullet's own opening verb when
> the rewrite only moved it into the past. That guard can only put back a
> word already in the bullet, so it stays within the core rule.

**Changed files**

- Analysis: `M` app/analysis/rewriter.py
- Docs: `M` docs/ACTION_ITEMS.md
- Tests: `M` tests/unit/test_rewriter.py

**Structure delta**

- `app/analysis/rewriter.py`: added `_past_forms()`, `keep_present_tense()`

---

<!-- entry:2026-10-06T08:13:31+05:30 -->
## 2026-10-06 08:13 (+0530) · P9.23: JD values from the LLM must match whole terms, in the JD's own case

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The live academic persona run (P9.10) showed "r" in the keyword table for
> the JD's "R": _verbatim checked each LLM value against the JD with a plain
> case-insensitive search, so "R" was found as the "r" inside "Senior" and
> took that spelling. The same check let a skill through when it only sat
> inside a longer word ("Java" in "JavaScript"), which is exactly what the
> check exists to stop. Now it needs word boundaries (a plural still counts)
> and prefers the JD's exact capitalisation.

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Tests: `M` tests/unit/test_jd_analyzer_v2.py

---

<!-- entry:2026-10-06T07:46:16+05:30 -->
## 2026-10-06 07:46 (+0530) · Docs hook: stop CHANGE_LOG separators from piling up on every commit

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> _split_entries kept the "---" that _join put after each entry, and _join
> then added another, so every commit added one separator under every entry:
> the log had 7,000+ stray "---" lines (~17.8K lines for 126 entries). Trailing
> separators are now dropped when the log is read, and the existing log is
> rewritten once (entry text unchanged, checked by diff; 3.7K lines now).

**Changed files**

- Tests: `A` tests/unit/test_update_docs.py
- Tooling: `M` scripts/update_docs.py

---

<!-- entry:2026-10-06T07:45:19+05:30 -->
## 2026-10-06 07:45 (+0530) · P9.22: Groq strict-JSON rejections fall back to plain JSON mode, readable error

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The owner's live run lost 11 of 14 rewrites: Groq answered every try with
> 400 json_validate_failed and an empty failed_generation, because the retry
> only ever re-sent strict json_schema mode. After two strict rejections the
> last try now uses json_object mode with our own Pydantic validation and
> retry. If every try is rejected, the error is a plain sentence ("usually
> temporary: start over") instead of Groq's raw JSON, since the Review banner
> shows it verbatim. Not reproduced afterwards (29 strict calls on the private
> resume passed), so the cause is intermittent on Groq's side.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- LLM: `M` app/llm/client.py
- Tests: `M` tests/unit/test_llm_client.py

---

<!-- entry:2026-10-05T22:10:16+05:30 -->
## 2026-10-05 22:10 (+0530) · P9.11: live-AI browser walkthrough (LIVE=1): wait countdown, Review tally, downloads

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Offline walkthroughs can't show what the real AI service does to the flow.
> walkthrough.cjs gets a LIVE mode for the real app on 8010: one combination,
> drafting allowed up to 6 minutes, the wait countdown recorded while drafting,
> Review's cards tallied by state, and both downloads saved and sized (in every
> mode). The live nurse run with Groq hit a real wait: one countdown line,
> cleared when drafting went on; everything else passed.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Tooling: `M` scripts/walkthrough.cjs

---

<!-- entry:2026-10-05T22:06:52+05:30 -->
## 2026-10-05 22:06 (+0530) · P9.16: executive persona: comma titles over a company line, stuffing relative to the source

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Two causes behind the executive case's strict xfail. The ATS template prints
> the company alone under "Title<tab>dates" when there's no location, and reading
> it back, the comma rule (P8.5) split "SVP, Global Supply Chain" into title and
> company. A short Title-Case line followed by a bullet now marks the comma title
> as whole. And the persona repeats the same bullets in all seven jobs, so "SAP"
> appeared 7 times in the source: the stuffing check now flags only repeats beyond
> what the resume itself had. Executive is off FULL_XFAIL.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` app/eval/harness.py
- Tests: `M` tests/integration/test_eval_cases.py, `M` tests/integration/test_persona_cases.py, `M` tests/unit/test_job_lines_p85.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._next_is_company_line()`

---

<!-- entry:2026-10-05T21:59:21+05:30 -->
## 2026-10-05 21:59 (+0530) · P9.21: a well-known city after the company is the location ("Infosys Ltd, Bengaluru")

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The live india run read "Senior Software Engineer, Infosys Ltd, Bengaluru" as
> company "Infosys Ltd, Bengaluru" with no location. A lone city was kept with the
> company on purpose, because "Groupe SEB, Lyon" and "Payments Platform, Stripe"
> have the same shape. A small list of large cities, and a place-like name right
> after a company suffix (Ltd, Inc, Pvt...), now settle it; unknown names still
> stay with the company.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Tests: `M` tests/unit/test_job_lines_p85.py

---

<!-- entry:2026-10-05T21:51:17+05:30 -->
## 2026-10-05 21:51 (+0530) · P9.20: multi-word keywords also match slash parts ("Oracle PL/SQL" shows Oracle SQL)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The live india run reported "Oracle SQL" missing next to "Maintained Oracle
> PL/SQL procedures". P9.15 split slash-joined words for exact sequences, but the
> "all words in one sentence" check for multi-word terms still looked only at
> whole tokens. It now uses the slash parts too.

**Changed files**

- Analysis: `M` app/analysis/keyword_match.py
- Docs: `M` docs/ACTION_ITEMS.md
- Tests: `M` tests/unit/test_keyword_match.py

---

<!-- entry:2026-10-05T21:49:17+05:30 -->
## 2026-10-05 21:49 (+0530) · P9.19: the change log lists only real rewrites; kept bullets are counted (P9.10 sales run)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> In the live sales-pdf run the AI kept 5 already-quantified bullets as written,
> and the downloadable changes.md showed "Accepted Rewrites (5)" with identical
> Original and Tailored text, which reads as if something changed. Only reworded
> items are listed now; the rest are counted as kept as written. P9.10's notes
> record the nurse and sales-pdf runs.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_tailor_resume_flow.py

---

<!-- entry:2026-10-05T21:47:14+05:30 -->
## 2026-10-05 21:47 (+0530) · P9.18: no "Skills:" label when the only skills category is named like the heading

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The live nurse run printed "SKILLS" and then "Skills: Epic, Cerner, ...": the
> resume's skills are one unnamed list, which the parser files under "Skills",
> and the template printed that name again. A lone, generically named category
> now prints just the list; resumes with several categories keep their labels.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/layout.py, `M` app/rendering/template_renderer.py
- Tests: `M` tests/unit/test_template_layout.py

**Structure delta**

- `app/rendering/layout.py`: added `skill_label()`

---

<!-- entry:2026-10-05T21:38:15+05:30 -->
## 2026-10-05 21:38 (+0530) · P9.17: count each LLM call once in the run report's usage (P9.10 nurse run)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The live nurse run's changes.md reported 8 calls / 20.4K tokens; the run made 4
> calls / 10.2K. When one client both drafts and generates (CLI and eval),
> proposal_usage and the final summary hold the same calls, and _merge_usage
> added them up. The two call lists are now joined by identity and the totals
> recomputed, so token budgets read from the report are real.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_tailor_resume_flow.py

---

<!-- entry:2026-10-05T21:36:15+05:30 -->
## 2026-10-05 21:36 (+0530) · P9.15: keyword match reads custom sections and slash-joined words (P9.10 nurse run)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The first live persona run (nurse) failed on attainable keyword coverage: "ICU"
> (under Clinical Rotations) and "NLC" (in "Compact/NLC") were reported missing
> although the resume says both, and "Arizona" was counted as attainable while
> the matcher deliberately skips places (P8.17).
>
> The matcher now reads the verbatim sections (other_sections) and also matches
> each part of a slash-joined word; the eval's attainable list skips places.
> Offline, eight of the eleven strict persona xfails now pass; academic, federal
> and executive keep specific reasons, and executive's becomes P9.16.

**Changed files**

- Analysis: `M` app/analysis/keyword_match.py
- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` app/eval/harness.py
- Tests: `M` tests/integration/test_persona_cases.py, `M` tests/unit/test_keyword_match.py

---

<!-- entry:2026-10-05T21:18:59+05:30 -->
## 2026-10-05 21:18 (+0530) · P9.14: landing: tailor / check the match are the form's actions, after the inputs (R4)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The owner saw "Tailor my resume" / "Just check my match" above the resume and JD
> boxes, as a mode switch, while the button that actually started the run sat at the
> bottom of the form. It read as a choice made before there was anything to act on.
>
> The form now ends with the two actions, one click each: Tailor my resume (the
> form's submit) and Just check my match. The output format is always shown and
> says it only applies to the tailored resume. Only the pressed action shows its
> busy text. The hero keeps a single "Get started" that scrolls to the form.
> The walkthrough clicks the new button and checks the actions follow the inputs.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` web/src/App.test.tsx, `M` web/src/components/UploadForm.test.tsx, `M` web/src/components/UploadForm.tsx, `M` web/src/pages/Landing.tsx
- Tooling: `M` scripts/walkthrough.cjs

---

<!-- entry:2026-10-05T20:35:20+05:30 -->
## 2026-10-05 20:35 (+0530) · P9.8: the CLI tests' subprocess keeps no run folders either (RUNS_DIR)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A full-suite run still left one data/runs folder: test_cli_parity starts
> the real CLI as a subprocess, which the conftest patch can't reach.
> RunManager now takes its folder from RUNS_DIR (default data/runs), and the
> test suite points it at a temp dir, which subprocesses inherit. The full
> suite (593 passed) now leaves data/runs empty.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Services: `M` app/services/run_manager.py
- Tests: `M` tests/conftest.py

---

<!-- entry:2026-10-05T20:29:20+05:30 -->
## 2026-10-05 20:29 (+0530) · P9.13: Arrange: projects inside a job move as blocks with their bullets

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The owner's screenshot (R3): the resume shows project sub-headings inside a
> job ("Scalable MLOps Framework", "Healthcare CRM…"), but Arrange listed the
> job's bullets flat, so a project couldn't be moved as a whole and a bullet
> could be moved out of its project (which would split the heading in two).
>
> - arrange.ts: orderedGroups() reads a job's bullets as project blocks;
>   moveGroup() moves a block with all its bullets; moveBullet() and
>   dropBullet() stay within the bullet's own project.
> - Arrange.tsx: each project is a block with its heading and up/down
>   buttons (focus follows the move); unchanged for jobs without projects.
> - services/arrange.py: _keep_groups_together() keeps a sub-heading's
>   bullets together whatever order the client sends.
>
> Checked in Chrome on the replica resume and through the API: the
> re-rendered DOCX has the projects in the new order and reads back cleanly.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` web/src/lib/arrange.test.ts, `M` web/src/lib/arrange.ts, `M` web/src/pages/Arrange.tsx
- Services: `M` app/services/arrange.py
- Tests: `M` tests/integration/test_arrange.py

**Structure delta**

- `app/services/arrange.py`: added `_keep_groups_together()`

---

<!-- entry:2026-10-05T20:23:45+05:30 -->
## 2026-10-05 20:23 (+0530) · P9.12: skills guardrails: each confirmed skill under its own type, no traits

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The owner's run listed "ci, version control, unit tests, LLMs, Fast learner,
> deep curiosity about AI" under "Frameworks". A keyword ticked in Review's gap
> questions went to the first skills category whose name matched
> tool|framework|skill, whatever it was, in the JD analysis's lowercase.
>
> Now (deterministic, in skills_tailor):
> - skill_type() classifies a term as language / framework / tool / practice /
>   expertise from a vocabulary; skill_category() puts it under an existing
>   category of that type, or a new one named for the type ("Practices",
>   "Expertise"), and an unknown term under a general category or "Other
>   skills": never into a category of another type.
> - is_trait(): soft skills and traits are never listed as skills. The user
>   gets a note, and an example they write still becomes a fact-checked
>   bullet. infer_kind() marks such phrases soft even when the JD analysis
>   called them hard, so the question card can say so when one is ticked.
> - jd_spelling(): the JD's own spelling ("CI").

**Changed files**

- Analysis: `M` app/analysis/gap_questions.py, `M` app/analysis/skills_tailor.py
- Docs: `M` docs/ACTION_ITEMS.md
- Root: `A` web/src/components/GapQuestionCard.test.tsx, `M` web/src/components/GapQuestionCard.tsx
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_gap_questions.py, `A` tests/unit/test_skill_placement_p912.py

**Structure delta**

- `app/analysis/skills_tailor.py`: added `is_trait()`, `jd_spelling()`, `skill_category()`, `skill_type()`

---

<!-- entry:2026-10-05T20:06:48+05:30 -->
## 2026-10-05 20:06 (+0530) · P9.7, P9.8, P9.9: Stage M gate: tests keep no run folders, .gitkeep, review fixes

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Stage M gate: full suite 567 passed; private live run clean (golden parse,
> 12/12 bullets handled, 0 failed calls, 1 page); the wait countdown checked in
> Chrome at 1440 light and 390 dark through a new WALKTHROUGH_WAIT option in
> scripts/walkthrough_server.py.
>
> Fixes from the independent review:
> - The gate's own test run re-created data/runs folders with fixture resumes:
>   older tests build TailorService() on the CLI default. An autouse conftest
>   fixture now points RunManager's default at each test's tmp dir.
> - data/runs/.gitkeep was allowed by .gitignore but never committed, so git
>   status always showed data/runs/ as untracked. Committed.
> - "5+ years 2 months" reads oddly; the months are dropped after a "+".

**Changed files**

- Analysis: `M` app/analysis/summary_writer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Root: `A` data/runs/.gitkeep
- Tests: `M` tests/conftest.py, `M` tests/unit/test_summary_years_p99.py
- Tooling: `M` scripts/walkthrough_server.py

**Structure delta**

- `scripts/walkthrough_server.py`: added `WalkthroughService.generate_proposals()`, `class WalkthroughService`

---

<!-- entry:2026-10-05T20:02:39+05:30 -->
## 2026-10-05 20:02 (+0530) · P9.9: summary keeps the resume's own years, months included

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The owner decided the summary should reuse the years the resume states
> ("3.6 years"), not the figure computed from role dates ("4+ years"); they
> can still edit it in Review. SummaryWriter.years_claim already did this for
> their resume (both live P9.3 outputs say "3.6 years"), so this closes open
> issue 3. One gap: "3 years 7 months of experience" came back as "3 years"
> and, with the months in between, wasn't recognised as the career claim.
> Months are now kept.

**Changed files**

- Analysis: `M` app/analysis/summary_writer.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Tests: `A` tests/unit/test_summary_years_p99.py

---

<!-- entry:2026-10-05T20:01:36+05:30 -->
## 2026-10-05 20:01 (+0530) · P9.8: web runs keep nothing in data/runs; old run folders deleted

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Found while planning the next round: tailor_resume always created
> data/runs/<id>/ with a copy of the uploaded resume, the JD, the parsed resume
> and the plan, and nothing ever deleted it. Every web visitor's resume stayed on
> the server, contradicting the privacy note ("kept only for this visit"). The
> run's server path was also shown in the progress list.
>
> TailorService(keep_run=False) now has no RunManager and every run write goes
> through _save_run, which does nothing then. The web app, the walkthrough
> server and the eval harness use it (the eval's outputs already go to
> --out-dir; its run folders only duplicated inputs, the private resume
> included). The CLI keeps its run folder and prints it as before.
>
> The 588 existing run folders (54 MB) were deleted with the owner's approval.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` app/eval/harness.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_privacy_p98.py
- Tooling: `M` scripts/walkthrough_server.py
- Web API: `M` app/api/main.py

**Structure delta**

- `app/services/tailor.py`: added `TailorService._save_run()`

---

<!-- entry:2026-10-05T19:59:02+05:30 -->
## 2026-10-05 19:59 (+0530) · P9.7: drafting screen: AI waits as one countdown, honest time, real plurals

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The owner's screenshot (R1): "usually under a minute" while the run waited
> on Groq, every wait stacked as a new ticked row (so the still-running
> rewrite looked done), and "10 bullet(s)". Since P9.3 per-minute waits of
> 30-65 s are waited out, so drafting takes 1-2 minutes.
>
> - LLMClient.on_wait now gets a WaitNotice: a str subclass carrying the
>   seconds, so the CLI log and other callers see the same plain message.
> - The SSE stream sends it as a `wait` event; streamStep passes the seconds.
> - ProgressPanel shows one countdown line under the running step, replaced
>   by the next wait and cleared by the next step; screen readers hear it once.
> - The drafting text says 1-2 minutes, longer when the AI asks us to wait.
> - "Rewriting 1 bullet / 10 bullets".

**Changed files**

- Analysis: `M` app/analysis/rewriter.py
- Docs: `M` docs/ACTION_ITEMS.md
- LLM: `M` app/llm/client.py
- Root: `M` web/src/components/Icon.tsx, `A` web/src/components/ProgressPanel.test.tsx, `M` web/src/components/ProgressPanel.tsx, `M` web/src/lib/api.ts, `M` web/src/pages/Details.tsx, `M` web/src/pages/Review.tsx
- Tests: `M` tests/unit/test_llm_client.py, `A` tests/unit/test_progress_p97.py
- Web API: `M` app/api/routes.py

**Structure delta**

- `app/analysis/rewriter.py`: added `_count()`
- `app/api/routes.py`: added `_progress_event()`
- `app/llm/client.py`: added `WaitNotice.__new__()`, `class WaitNotice`

---

<!-- entry:2026-10-04T13:55:45+05:30 -->
## 2026-10-04 13:55 (+0530) · P9.3: private real-resume run passes; per-minute 429s and reasoning cut-offs retried

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The final live run of the owner's resume against the FOX JD first lost 5 of
> 12 bullets to llm_error. Two causes, both in the Groq client:
>
> - gpt-oss spent its completion budget on reasoning and Groq rejected the
>   call ("max completion tokens reached before generating a valid
>   document"). A strict-JSON retry after that now steps the reasoning effort
>   down (high -> medium -> low) so the JSON fits.
> - Any 429 asking for more than 30 s failed at once. That was meant for the
>   daily limit, but the free tier's tokens-per-minute limit asks for 37-41 s
>   when role rewrites run together. Per-minute waits up to 65 s are now waited
>   out; the daily limit (or anything longer) still fails fast.
>
> After the fixes: parse = golden, 12/12 bullets handled (9 rewritten, 3 kept),
> 0 errors, 100% coverage, clean DOCX/PDF read-back, 1 page. Arrange and
> re-render on the same resume also passed. Private inputs and outputs stay in
> data/eval/private/ (gitignored); only aggregate counts are recorded.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- LLM: `M` app/llm/client.py
- Tests: `M` tests/unit/test_llm_client.py

**Structure delta**

- `app/llm/client.py`: added `_too_long_to_wait()`

---

<!-- entry:2026-10-04T13:43:51+05:30 -->
## 2026-10-04 13:43 (+0530) · P9.4: browser walkthrough at 1440/390 px, light and dark; three UI fixes

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> No Phase 8 stage had browser automation. playwright-core was already in
> web/node_modules and Chrome is installed, so the walkthrough now runs in a
> real browser: the whole flow on the nurse persona, at 1440 and 390 px, in
> light and dark, with a keyboard move and a mouse hide + Undo in Arrange.
> The server uses the offline eval LLM so it costs no Groq quota.
>
> Result: 0 console errors, 0 x 5xx, no horizontal overflow; Check details
> shows "Also read" and no heading-as-unplaced lines (P9.1 F1 seen fixed).
>
> Fixed from the screenshots:
> - "Arrange and edit" wrapped onto two lines in its box at 1440.
> - With the stretch guidance now on Results (P9.5), "rewrites only reword
>   what's already there" was said twice; the second line is dropped then.
> - The AI-unavailable banner ended in a stray "Then start over." when the
>   provider has no fix hint.
>
> scripts/walkthrough.cjs + scripts/walkthrough_server.py make it repeatable.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` web/src/pages/Results.test.tsx, `M` web/src/pages/Results.tsx, `M` web/src/pages/Review.tsx
- Tooling: `A` scripts/walkthrough.cjs, `A` scripts/walkthrough_server.py

**Structure delta**

- new module `scripts/walkthrough_server.py`

---

<!-- entry:2026-10-04T13:28:14+05:30 -->
## 2026-10-04 13:28 (+0530) · P9.1: Stage L review fixes: headings as unplaced lines, language, file names, sweep

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A fresh review agent checked P8.22-P8.26 and reported six issues; each was
> reproduced and fixed with a test.
>
> - F1 (high): unplaced_lines() listed every section heading, Check details
>   defaulted each to "Additional information" and always sent it, so every
>   run added the headings to the output and rewrote the checked parse.
>   Section-opening headings are skipped, and "Leave it out" is a choice.
> - F2: an English resume full of Spanish names read as Spanish. Particles
>   inside a proper name ("Banco de España") don't count; at least 3 hits.
> - F3: a long JD company made a file name the OS refuses; parts are capped.
> - F4: sessions were swept only inside requests, so an idle server kept files
>   past the privacy note's promise. A lifespan task sweeps every minute. This
>   also exposed that create_app() ignored an empty SessionStore (falsy via
>   __len__). The note no longer says nothing is stored in the browser.
> - F5: a failed conversion leaked the upload and its temp folder.
> - F6: a wrong employer or a quarter of bullets lost on read-back is serious.
>
> Persona eval unchanged (41 pass, 11 xfail).

**Changed files**

- Analysis: `M` app/analysis/language.py
- Docs: `M` docs/ACTION_ITEMS.md
- Rendering: `M` app/rendering/layout.py
- Root: `M` web/src/pages/Details.tsx, `M` web/src/pages/Landing.tsx, `M` web/src/pages/PrivacyNote.test.tsx
- Tests: `M` tests/unit/test_api.py, `M` tests/unit/test_details_p826.py, `M` tests/unit/test_global_p825.py
- Validation: `M` app/validation/output.py
- Web API: `M` app/api/main.py, `M` app/api/routes.py

**Structure delta**

- `app/analysis/language.py`: added `_drop_name_particles()`
- `app/api/main.py`: added `_sweeping()`

---

<!-- entry:2026-10-04T13:17:40+05:30 -->
## 2026-10-04 13:17 (+0530) · P9.5: matching notes: connector acronyms, shared role word, clean spans, stretch guidance

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The four low-impact notes left by the Stage K review:
> - definitions() only skipped of/and/for/the, so "Or Associate (OA)" or
>   "With Teams (WT)" became definitions. Connectors now never give a letter or
>   start an expansion; an acronym whose letters include one ("Point Of Sale
>   (POS)") is caught by an all-words check, which used to miss it.
> - "Java or Python developer" let Java count alone but needed "Python
>   developer". A role or credential word ending the last option now lets that
>   option's head count alone too. Lenient rather than strict on purpose: making
>   "RN or LPN license" need "RN license" would cost nurses credit.
> - Requirement source spans were found with original.find() in the raw (maybe
>   HTML) JD while the job keeps the cleaned text, and always took the first
>   occurrence. They now index raw_text, searched from the previous span.
> - Results showed only the different-field guidance; the stretch one too now.
>
> The persona eval showed `veteran` passing its full check: it already did
> before this change (stale strict xfail since Stage K), so it's off the list.

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py, `M` app/analysis/keyword_match.py
- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` web/src/pages/Results.test.tsx, `M` web/src/pages/Results.tsx
- Tests: `M` tests/integration/test_persona_cases.py, `M` tests/unit/test_jd_analyzer_v2.py, `A` tests/unit/test_matching_p95.py

---

<!-- entry:2026-10-04T13:09:56+05:30 -->
## 2026-10-04 13:09 (+0530) · P9.2: edge-file sweep: damaged .doc/.rtf refused, empty files named, 60 s convert cap

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The 2026-10-03 sweep hung with no output. Re-run one request at a time with a
> 60 s curl cap on a fresh 8010 server (dead AI key, so no Groq quota): 23 files
> plus pasted text, no hang reproduced, slowest 19 s.
>
> What it did find:
> - A damaged .doc (or binary .rtf) with valid magic bytes came back as a 200
>   "resume" full of garbage characters: LibreOffice falls back to its plain-text
>   importer. The import filter is now forced per type (MS Word 97 / writer8 /
>   Rich Text Format), and RTF / .txt whose bytes are >2% control characters
>   are refused as damaged before conversion (RTF is text, so a forced filter
>   can't catch it).
> - A 0-byte upload said "doesn't look like a real .docx"; now "This file is empty".
> - A .doc that is really RTF (Word can save that) was refused; now converted as RTF.
> - Upload conversions are capped at 60 s instead of 120, so a stuck LibreOffice
>   can't keep a request open for two minutes.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Ingestion: `M` app/ingestion/errors.py
- Rendering: `M` app/rendering/pdf_converter.py
- Tests: `M` tests/unit/test_api.py, `M` tests/unit/test_uploads_p822.py
- Web API: `M` app/api/routes.py

**Structure delta**

- `app/api/routes.py`: added `_mostly_binary()`

---

<!-- entry:2026-10-03T20:34:36+05:30 -->
## 2026-10-03 20:34 (+0530) · P8.17, P8.18, P8.19, P8.20: Stage K review fixes; Stage L gate deferred

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent Stage K review found ways the score could still be gamed
> or misread: skills-list stuffing kept a high score, aliases missed plurals,
> requirement status was marked met from skills-only keywords, HTML tags and
> company names leaked into offline keywords, and the conditions checklist
> matched unrelated phrases. Each is fixed with a test. The remaining Stage L
> gate work (review re-run, edge-file sweep, real-resume run, browser check)
> is recorded in ACTION_ITEMS for a later session.

**Changed files**

- Analysis: `M` app/analysis/checklist.py, `M` app/analysis/jd_analyzer.py, `M` app/analysis/keyword_match.py, `M` app/analysis/terminology.py
- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` web/src/components/ConditionList.test.tsx, `M` web/src/components/ConditionList.tsx

---

<!-- entry:2026-10-03T14:08:05+05:30 -->
## 2026-10-03 14:08 (+0530) · P8.23, P8.24, P8.25, P8.26: degraded states, privacy, global basics, Check details

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Stage L of the user-testing plan:
> - P8.23: rate-limit waits show in the progress list instead of a silent
>   stall; a used-up daily AI limit is remembered and explained ("Today's
>   free AI limit is used up ... about 1 h 30 min"); the match report says
>   whether the AI read the JD.
> - P8.24: a privacy note before upload says the text goes to Groq's cloud
>   AI and files are deleted at the end of the visit; README no longer says
>   "local-first".
> - P8.25: a CJK name rendered blank in the PDF (a fallback font now covers
>   other scripts); file names keep accented and non-Latin letters and drop
>   "_Company" when unknown; a German or Spanish resume or JD is named as
>   "English only for now" instead of a silent 0%.
> - P8.26: Check details shows everything read from the file and lets the
>   user place lines the parse couldn't; parse issues are in plain words;
>   only serious read-back problems fail a run (most persona runs ended
>   "with warnings" from minor template differences); HTML download;
>   non-tech placeholders and a gentler numbers nudge.

**Changed files**

- Analysis: `A` app/analysis/language.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- LLM: `M` app/llm/client.py
- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/layout.py, `M` app/rendering/template_renderer.py
- Root: `M` README.md, `M` web/src/App.tsx, `M` web/src/components/AddJobForm.tsx, `M` web/src/lib/api.ts, `M` web/src/lib/store.ts, `M` web/src/lib/types.ts, `M` web/src/pages/Details.tsx, `M` web/src/pages/Landing.tsx, `A` web/src/pages/PrivacyNote.test.tsx, `M` web/src/pages/Report.tsx, `M` web/src/pages/Results.tsx, `M` web/src/pages/Review.tsx
- Services: `M` app/services/tailor.py
- Tests: `M` tests/conftest.py, `M` tests/unit/test_api.py, `A` tests/unit/test_details_p826.py, `A` tests/unit/test_global_p825.py, `M` tests/unit/test_llm_client.py
- Validation: `M` app/validation/content_lint.py, `M` app/validation/output.py
- Web API: `M` app/api/routes.py

**Structure delta**

- new module `app/analysis/language.py`
- `app/api/routes.py`: added `_resume_texts()`, `plain_issue()`, `unplaced_lines()`
- `app/llm/client.py`: added `class LLMDailyLimitError`, `daily_limit_message()`
- `app/rendering/layout.py`: added `fallback_font()`, `needs_fallback_font()`
- `app/validation/output.py`: added `OutputQAValidator.is_serious()`

---

<!-- entry:2026-10-03T13:21:17+05:30 -->
## 2026-10-03 13:21 (+0530) · P8.19, P8.21: Stage K gate fixes: quarter credit for skills-only, field note

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The Stage K gate still saw the user test's keyword-stuffed resume beat a
> real account executive (50% vs 36%) at half credit for skills listed but
> never shown in the work; it now gets a quarter (25% vs 36%). The
> "different field" note fired on same-field personas whose JD title the
> offline analysis couldn't read; it now needs a known title with nothing
> in common. Live and offline scores agree within 7 points on three
> personas (the user test saw 16-18).

**Changed files**

- Analysis: `M` app/analysis/keyword_match.py
- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` web/src/components/KeywordList.tsx
- Tests: `M` tests/unit/test_stuffing_p819.py

---

<!-- entry:2026-10-03T12:46:46+05:30 -->
## 2026-10-03 12:46 (+0530) · P8.22: plain messages for broken uploads; .txt, pasted text and .doc/.odt/.rtf

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A corrupt .docx or a password-protected PDF ended in an unhandled 500
> ("Something went wrong on our side"), a scanned PDF parsed as empty, and
> .doc, .txt, .rtf and .odt files were refused. Each unreadable file now
> gets a specific message, plain text is read (an upload or text pasted
> in the form), and .doc / .odt / .rtf are converted to .docx on upload.
>
> LibreOffice conversions now draw from a pool of warm profiles, never
> shared by two conversions at once: one fresh profile per conversion cost
> about five seconds each, and the default profile could be blocked by a
> LibreOffice already running on the machine.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Ingestion: `A` app/ingestion/errors.py, `A` app/ingestion/text.py
- Rendering: `M` app/rendering/pdf_converter.py
- Root: `M` web/src/components/UploadForm.test.tsx, `M` web/src/components/UploadForm.tsx
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_api.py, `A` tests/unit/test_uploads_p822.py
- Tooling: `M` scripts/update_docs.py
- Web API: `M` app/api/routes.py

**Structure delta**

- new module `app/ingestion/errors.py`: `class UnreadableFile`
- new module `app/ingestion/text.py`: `class TextParser`
- `app/rendering/pdf_converter.py`: added `_give_back()`, `_take_profile()`, `convert_to_docx()`
- `app/services/tailor.py`: added `TailorService.read_file()`

---

<!-- entry:2026-10-03T12:42:26+05:30 -->
## 2026-10-03 12:42 (+0530) · P8.21: explain a low match; career-change guidance

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A nurse applying for a sales job scored 0 and a teacher moving into
> instructional design 16%, and both were shown the same "aim for 75-85%"
> target with no reason. The match now carries guidance: a job in a
> different field (a low rate and no title word in common) is named as
> such, with why rewording can't change it and honest career-change steps;
> a stretch gets its own short note. Shown on the match report and Results.

**Changed files**

- Analysis: `M` app/analysis/keyword_match.py
- Docs: `M` docs/ACTION_ITEMS.md
- Domain models: `M` app/domain/report.py
- Root: `A` web/src/components/MatchGuidance.tsx, `M` web/src/lib/types.ts, `M` web/src/pages/Report.tsx, `M` web/src/pages/Results.tsx
- Tests: `A` tests/unit/test_guidance_p821.py

**Structure delta**

- `app/analysis/keyword_match.py`: added `guidance()`

---

<!-- entry:2026-10-03T05:55:32+05:30 -->
## 2026-10-03 05:55 (+0530) · P8.20: a checklist for job conditions that aren't keywords

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> State licences, clearances, shift availability, lifting, a driver's
> licence, languages and minimum years were invisible: a keyword match
> can't show them and a resume often shouldn't list them. They now form a
> checklist built in code from the JD's own lines: years are checked
> against the dated roles, the user ticks the rest once on Review, and the
> match report lists them. They never change the resume or the match rate;
> the confirmed ones are recorded in the change log.

**Changed files**

- Analysis: `A` app/analysis/checklist.py
- Docs: `M` docs/ACTION_ITEMS.md
- Domain models: `M` app/domain/report.py
- Root: `A` web/src/components/ConditionList.test.tsx, `A` web/src/components/ConditionList.tsx, `M` web/src/lib/api.ts, `M` web/src/lib/review.ts, `M` web/src/lib/types.ts, `M` web/src/pages/Report.tsx, `M` web/src/pages/Review.tsx
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_checklist_p820.py
- Tooling: `M` scripts/update_docs.py
- Web API: `M` app/api/routes.py

**Structure delta**

- new module `app/analysis/checklist.py`: `class Condition`

---

<!-- entry:2026-10-03T05:48:54+05:30 -->
## 2026-10-03 05:48 (+0530) · P8.19: skills listed but never shown in the work earn half credit

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A barista with one Skills line pasted from the job description scored
> 87.5%, against 37.5% for a strong account executive, because a keyword
> in the Skills list counted the same as one shown in the work. Such a
> keyword now earns half its weight and its chip says so; certifications
> and degrees in their own sections still count fully.

**Changed files**

- Analysis: `M` app/analysis/keyword_match.py
- Docs: `M` docs/ACTION_ITEMS.md
- Domain models: `M` app/domain/report.py
- Root: `M` web/src/components/KeywordList.tsx, `M` web/src/lib/types.ts
- Tests: `A` tests/unit/test_stuffing_p819.py

---

<!-- entry:2026-10-03T05:39:16+05:30 -->
## 2026-10-03 05:39 (+0530) · P8.18: clean JD text, no perks as keywords, a fairer offline fallback

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> An HTML job description produced the keyword "h2" and the title
> "🚀 Senior Accountant 💼"; benefits words (Dental, Vision, PTO, ADA)
> were scored as skills; offline, lowercase trade terms were lost and
> multi-word terms split ("Supply" "Chain"); a two-word JD scored 100%; and
> a requirement could read "not shown" while all its keywords were found
> (P1.16).
>
> JD text is now cleaned of tags, entities and emoji before analysis,
> perks and equal-opportunity text never yield keywords, the fallback
> keeps field terms and capitalised phrases, very short JDs are refused,
> a rules-based score is labelled approximate, and requirement statuses
> follow the keyword table.

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py, `M` app/analysis/keyword_match.py, `M` app/analysis/terminology.py
- Docs: `M` docs/ACTION_ITEMS.md
- Domain models: `M` app/domain/report.py
- Root: `M` app/eval/harness.py, `M` web/src/lib/types.ts, `M` web/src/pages/Report.tsx, `M` web/src/pages/Results.tsx
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_api.py, `A` tests/unit/test_jd_p818.py
- Web API: `M` app/api/routes.py

**Structure delta**

- `app/analysis/jd_analyzer.py`: added `JDAnalyzer._not_benefit()`, `JDAnalyzer.clean_text()`, `JDAnalyzer.too_short()`
- `app/analysis/keyword_match.py`: added `reconcile()`

---

<!-- entry:2026-10-03T05:18:05+05:30 -->
## 2026-10-03 05:18 (+0530) · P8.13, P8.15, P8.16: Stage J review fixes

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review of the arrange-and-edit step (PASS WITH ISSUES)
> reproduced ten problems: hiding Work Experience or emptying a job's
> bullets failed the run (false "lost" lines, a job title with nothing
> under it); a failed tailoring run left the old arrangement usable; a
> change made within the update pause was lost on leaving; Undo left the
> status waiting; dragging a bullet could move a whole section; focus fell
> to the page after a move; section moves stalled on sections the screen
> doesn't show; "Reset" pointed at the user's own layout after reopening;
> and changes.md grew with every arrangement.
>
> All fixed with tests; reworded bullets are also never trimmed, and
> trimmed bullets are marked where they belong.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` web/src/lib/arrange.ts, `M` web/src/lib/types.ts, `M` web/src/pages/Arrange.test.tsx, `M` web/src/pages/Arrange.tsx
- Services: `M` app/services/arrange.py, `M` app/services/tailor.py
- Tests: `M` tests/integration/test_arrange.py
- Web API: `M` app/api/routes.py

**Structure delta**

- `app/services/arrange.py`: added `_had_bullets()`, `emptied()`

---

<!-- entry:2026-10-03T05:07:36+05:30 -->
## 2026-10-03 05:07 (+0530) · P8.17: fairer matching: alternatives, slash terms, acronyms, degrees, places

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The score was unfair outside tech: "OSHA 10 or 30" never matched "OSHA
> 30", "Salesforce CRM" missed with "Salesforce" on the resume, GAAP didn't
> match its expansion, a Master's didn't meet "Bachelor's degree", accented
> keywords were cut short, and places like "Arizona" counted as hard
> skills.
>
> Alternatives and slash terms now get credit, acronyms are linked to their
> expansions (a built-in list plus "Full Name (ACR)" found in the texts),
> degrees follow their level, a product name with a generic tail counts by
> the name, tokens are read in any script, and places are left out.

**Changed files**

- Analysis: `M` app/analysis/gap_questions.py, `M` app/analysis/jd_analyzer.py, `M` app/analysis/keyword_match.py, `M` app/analysis/terminology.py
- Docs: `M` docs/ACTION_ITEMS.md
- Tests: `A` tests/unit/test_matching_p817.py

**Structure delta**

- `app/analysis/keyword_match.py`: added `KeywordMatcher.__init__()`, `KeywordMatcher._found_with_credit()`, `KeywordMatcher._slash_parts()`, `alternatives_of()`, `definitions()`, `is_place()`

---

<!-- entry:2026-10-03T04:30:48+05:30 -->
## 2026-10-03 04:30 (+0530) · P5.7: a separate LibreOffice profile per PDF conversion

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Two conversions at once on LibreOffice's shared default profile make the
> second fail, which the Stage J real-resume run hit (a review was
> converting at the same moment): the arranged file had no PDF and failed
> the read-back. Two visitors, or a page-fit loop beside another run, do
> the same in the web app. Each conversion now gets its own temporary
> profile, removed afterwards; four parallel conversions pass. Listed under
> the shelved P5.7 hosting item, which otherwise stays open.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Rendering: `M` app/rendering/pdf_converter.py

---

<!-- entry:2026-10-03T03:53:04+05:30 -->
## 2026-10-03 03:53 (+0530) · P8.13, P8.14, P8.16: arrange-and-edit backend; no silent reordering

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The owner asked for a plug-and-play step after the AI changes: reorder
> sections, jobs and bullets, hide sections, edit text and bring back what
> page-fit trimmed. Tailoring now keeps the resume as it was before
> page-fit plus a default layout, and POST /api/arrange applies the user's
> layout and re-renders with no LLM call, running page-fit (pinned items
> are never trimmed; "don't trim" renders once), the ATS round-trip and
> the coverage check. A bullet can only move within its own job.
>
> Bullets are no longer reordered by relevance when nothing was accepted,
> and page-fit's notes name the job each trim came from.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Rendering: `M` app/rendering/page_fit.py
- Services: `A` app/services/arrange.py, `M` app/services/tailor.py
- Tests: `A` tests/integration/test_arrange.py, `M` tests/unit/test_api.py
- Tooling: `M` scripts/update_docs.py
- Web API: `M` app/api/routes.py

**Structure delta**

- `app/api/routes.py`: added `_results_out()`, `arrange()`, `class ArrangeIn`
- `app/rendering/page_fit.py`: added `_owner_label()`
- new module `app/services/arrange.py`: `class Layout`
- `app/services/tailor.py`: added `TailorService.arrange()`, `_hidden_text()`

---

<!-- entry:2026-10-03T03:50:00+05:30 -->
## 2026-10-03 03:50 (+0530) · P8.9, P8.10, P8.12: Stage I gate and review fixes

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Live gate (5 LLM personas): no accepted rewrite borrows the JD's wording
> or takes a fact from another job, and borrowed summaries were rejected.
> It also showed "experience" and "certifications" counted as borrowed,
> "Troubleshoot -> Troubleshot" as a dropped word, and two read-back quirks.
>
> The independent review (PASS WITH ISSUES) reproduced nine more: plain
> words moved from another job passed; gap questions hid real gaps through
> a head-token rule and a degree check run on every keyword; opt-in
> summaries were applied by the direct CLI run and the eval; the summary
> check rejected its own prompt's phrasing; one generic JD-only word
> rejected faithful rewrites, and US / UK spellings differed; a licence or
> degree counted as "another job"; hyphenated words skipped the checks;
> years_claim took the first number; and offline every gap keyword was a
> "hard" skill, so licences went to Skills. All fixed with tests.

**Changed files**

- Analysis: `M` app/analysis/gap_questions.py, `M` app/analysis/resume_normalizer.py, `M` app/analysis/summary_writer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` app/eval/harness.py, `M` web/src/components/GapQuestionCard.tsx, `M` web/src/lib/types.ts
- Services: `M` app/services/tailor.py
- Tests: `M` tests/integration/test_persona_cases.py, `M` tests/unit/test_fact_check_p89.py, `M` tests/unit/test_gap_questions.py, `M` tests/unit/test_stage_h_review.py, `M` tests/unit/test_summary_writer.py
- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/analysis/gap_questions.py`: added `infer_kind()`
- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._ends_with_suffix()`
- `app/validation/factual.py`: added `FactualValidator._content_tokens()`, `FactualValidator._is_plain()`, `FactualValidator._words_from_elsewhere()`

---

<!-- entry:2026-10-03T03:30:21+05:30 -->
## 2026-10-03 03:30 (+0530) · P8.12: gap questions worded by kind; skip what the resume already shows

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Gap questions were one template for everything ("Have you worked with
> Bachelor's degree preferred?", "...with OSHA 10 or 30?") and asked about
> things already on the resume (Salesforce for "Salesforce CRM", NLC for
> "Compact/NLC"). A ticked certificate landed in Skills, and ticking with
> no answer silently doubled the score.
>
> Questions are now worded for licences, degrees, soft skills and tools;
> alternatives, slash terms, the head of a multi-word term and lower degrees
> the resume already shows are not asked; a ticked licence goes under
> Certifications, a degree is never a skill, and a tick without a line
> saying where is flagged on the card and in the run notes.

**Changed files**

- Analysis: `M` app/analysis/gap_questions.py
- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` web/src/components/GapQuestionCard.tsx, `M` web/src/lib/types.ts
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_gap_questions.py

**Structure delta**

- `app/analysis/gap_questions.py`: added `_degree_level()`, `_wording()`, `partly_shown()`

---

<!-- entry:2026-10-03T03:25:58+05:30 -->
## 2026-10-03 03:25 (+0530) · P8.11: rewrites keep the field's own voice; no JD wording swap

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Rewrites flattened domain language: "Precept new graduate nurses" became
> "Educated 8 new graduate nurses", "Closed largest deal in company
> history" became "Closed largest company deal", "Built pipeline" became
> "Managed pipeline". The prompt also asked for the requirement's own
> wording, which P8.9 now rejects when only the job description uses it.
>
> The prompt now writes in the resume's own field, keeps specific verbs and
> claims, uses JD keywords only where the bullet already says them, and
> doesn't push numbers onto unmeasured work. The fact check flags a dropped
> superlative.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- LLM: `M` app/llm/prompts/rewrite_role.txt
- Tests: `M` tests/unit/test_fact_check_p89.py
- Validation: `M` app/validation/factual.py

---

<!-- entry:2026-10-03T03:23:32+05:30 -->
## 2026-10-03 03:23 (+0530) · P8.10: field-neutral summary; the resume's own years; keep the user's summary

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The summary prompt asked for "Builds and deploys ... using X, Y and Z",
> which produced "Builds and delivers patient care using Epic, RN, ICU and
> BLS", put parse garbage ("03/") in as the title, stated years that
> contradicted the resume (7 vs 10+), and replaced good original summaries.
>
> The prompt now works for any field and names licences only as
> credentials; code passes the resume's own stated years, a title that
> passes a sanity check, and marks the proposal opt-in when the resume has
> a summary, so the user's own text stays unless they choose the new one.

**Changed files**

- Analysis: `M` app/analysis/change_proposal.py, `M` app/analysis/summary_writer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Entry points: `M` app/cli.py
- LLM: `M` app/llm/prompts/summary.txt
- Root: `M` web/src/lib/review.test.ts, `M` web/src/lib/review.ts, `M` web/src/lib/types.ts
- Tests: `M` tests/unit/test_summary_writer.py
- Web API: `M` app/api/routes.py

**Structure delta**

- `app/analysis/summary_writer.py`: added `SummaryWriter.sane_title()`, `SummaryWriter.years_claim()`

---

<!-- entry:2026-10-03T03:19:56+05:30 -->
## 2026-10-03 03:19 (+0530) · P8.3, P8.5, P8.8: Stage H review fixes for ordinary tech resumes

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review of Stage H found six regressions, all reproduced:
> all-caps or Word-heading sub-headings (a school, a project, a certificate)
> opened kept sections and dropped whole Projects / Education entries while
> coverage said 100%; a sentence mentioning "from 2020 to 2023" became a job;
> "School line, then degree line" split in two; merged skill categories and
> dropped sub-headings failed coverage; a headline was taken as the location;
> a ZIP+4 was read as the phone and "ASP.NET" as a link.
>
> Unknown headings now open a kept section only where no section was
> recognised; mid-line date ranges need a short header and a separator; a
> one-line education entry needs a school name; coverage ignores merged
> labels and removed sub-headings; locations need a real state code and are
> never titles; ZIP codes and capitalised framework names are skipped. US
> and EU numeric dates are told apart per range, and kept sections print
> where they were in the file.

**Changed files**

- Analysis: `M` app/analysis/experience.py, `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Domain models: `M` app/domain/resume.py
- Rendering: `M` app/rendering/layout.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_education_p88.py, `M` tests/unit/test_job_lines_p85.py, `A` tests/unit/test_stage_h_review.py
- Validation: `M` app/validation/coverage.py

**Structure delta**

- `app/analysis/experience.py`: added `day_first()`
- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._header_range()`
- `app/rendering/layout.py`: added `_place_kept_sections()`

---

<!-- entry:2026-10-03T02:34:29+05:30 -->
## 2026-10-03 02:34 (+0530) · P8.9: fact check v3: JD-only wording, facts from another job, new claims

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> In every English LLM run of the user test, rewrites and summaries
> borrowed the job description's wording ("adult learning theory",
> "e-learning modules") or claimed things the resume doesn't say ("Enhanced
> safety standards"), and a student ICU rotation became "Administered
> direct ICU patient care" under another job, all passing the fact check.
>
> Words that only the job description uses are now rejected in bullets and
> summaries (absorbing P1.15); a tool or name found only under a different
> job or section is rejected for this one; two or more new words the resume
> never uses need the user's check; and scope verbs follow one rule. The
> summary check also rejects a repeated phrase (used by P8.10).

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_fact_check_p89.py
- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/validation/factual.py`: added `FactualValidator._new_words()`, `FactualValidator._owner_prefix()`

---

<!-- entry:2026-10-03T01:28:56+05:30 -->
## 2026-10-03 01:28 (+0530) · P8.8: one-line education entries stay separate, newest first

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Two degrees written on two lines ("M.Ed. ..., Texas State University,
> 2019" then "B.S. ..., University of Texas, 2016") were merged into one
> entry, printed oldest first, and the round-trip warned about it. A line
> naming a degree and a school is now a whole entry; coursework and similar
> "Label: ..." lines stay with the entry above; entries are sorted newest
> first. Also fixed "Expected May 2026" printing as "Jan 2026".
>
> This completes Stage H: every persona keeps all its content, with each job
> read correctly.

**Changed files**

- Analysis: `M` app/analysis/experience.py, `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Rendering: `M` app/rendering/layout.py
- Tests: `M` tests/integration/test_persona_cases.py, `A` tests/unit/test_education_p88.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._split_education_line()`, `ResumeNormalizer._trim()`

---

<!-- entry:2026-10-03T01:19:45+05:30 -->
## 2026-10-03 01:19 (+0530) · P8.7: text boxes, middle-dot bullets, name from a separated header

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A job inside a Word text box vanished with no warning (Canva and many Word
> templates use them); text boxes are now read where they are anchored, each
> once. PDFs whose font lacks "•" print a middle dot, so their bullets were
> read as companies and ran together; "·" and other common glyphs are now
> bullet markers. The name in a "Name · Title · email" page header was
> fixed with the header work in P8.3.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Ingestion: `M` app/ingestion/docx.py, `M` app/ingestion/pdf.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/integration/test_persona_cases.py, `A` tests/unit/test_layouts_p87.py

**Structure delta**

- `app/ingestion/docx.py`: added `DocxParser._text_box_paragraphs()`

---

<!-- entry:2026-10-03T01:15:26+05:30 -->
## 2026-10-03 01:15 (+0530) · P8.5: job lines outside tech: comma formats, multi-line headers, role words

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Common job-line formats outside tech were misread: "Title, Company, City,
> dates" left the company empty, "Title<tab>Company" with dates on the next
> line put "03/" in the title, a 100+ character legal title became a bullet
> (merging a clerkship into the next job), a federal header spread over three
> lines became two jobs, and "Delivery Driver" or "Production Supervisor"
> swapped with the company because the role words were all tech titles.
>
> These now resolve to one job with title, company, location and dates;
> extra facts on a header line are kept verbatim as job details; and a later
> role never inherits a date column as its location. 15 of 22 personas now
> read correctly.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Domain models: `M` app/domain/resume.py
- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/template_renderer.py
- Tests: `M` tests/integration/test_persona_cases.py, `A` tests/unit/test_job_lines_p85.py
- Validation: `M` app/validation/output.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._next_is_meta_line()`, `ResumeNormalizer._split_comma_job()`, `ResumeNormalizer._split_company_location()`

---

<!-- entry:2026-10-03T01:03:44+05:30 -->
## 2026-10-03 01:03 (+0530) · P8.6: seasons, MM/YYYY, DD/MM/YYYY, ISO, 'YY and "till date" dates

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Many date formats outside the US tech norm were not read, which zeroed
> years of experience and with it the page target, the summary's years and
> the content checks: an EU CV's DD/MM/YYYY roles had no dates, "Till Date"
> and "heute" meant nothing, "Summer 2021" was lost. One date grammar in the
> parser now covers them, experience.py owns the "still in this role" words
> for every module, and a start date in the future is listed on Check
> details.

**Changed files**

- Analysis: `M` app/analysis/experience.py, `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Rendering: `M` app/rendering/layout.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_dates_p86.py
- Validation: `M` app/validation/content_lint.py

**Structure delta**

- `app/analysis/experience.py`: added `future_dates()`
- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._trailing_dates()`

---

<!-- entry:2026-10-03T00:57:34+05:30 -->
## 2026-10-03 00:57 (+0530) · P8.3: keep unknown sections verbatim; header details; licence lines whole

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A heading the parser didn't know sent its lines into the previous section
> or dropped them: German and Spanish CVs came out as a name and an email,
> publications became a fake job, bar admissions vanished. Such sections are
> now kept verbatim under their own heading (Resume.other_sections) and
> rendered in the DOCX and HTML, and a wider heading vocabulary routes
> licences, hobbies, honors, "journey" and "appointments" where they belong.
> New words only start a section on a line styled like the document's own
> headings, so bold labels inside Skills or a bold employer stay content.
>
> Header parts that are not contact data (address, date of birth,
> clearance) are kept as candidate details. Licence and certificate lines
> are split on commas only when no piece is a date, expiry or place.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Domain models: `M` app/domain/evidence.py, `M` app/domain/resume.py
- Rendering: `M` app/rendering/html_renderer.py, `M` app/rendering/layout.py, `M` app/rendering/template_renderer.py
- Tests: `M` tests/integration/test_persona_cases.py, `A` tests/unit/test_kept_sections_p83.py
- Validation: `M` app/validation/output.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._display_heading()`, `ResumeNormalizer._header_segments()`, `ResumeNormalizer._heading_kind()`, `ResumeNormalizer._heading_sig()`, `ResumeNormalizer._is_detail()`, `ResumeNormalizer._looks_like_location()`, `ResumeNormalizer._looks_like_name()`, `ResumeNormalizer._section_heading_sigs()`, `ResumeNormalizer._split_list_items()`, `ResumeNormalizer._styled_as_heading()`, `ResumeNormalizer.section_kind()`
- `app/domain/resume.py`: added `class OtherSection`, `class SectionLine`
- `app/rendering/html_renderer.py`: added `HtmlResumeRenderer._other()`
- `app/rendering/layout.py`: added `ordered_sections()`, `other_section()`
- `app/rendering/template_renderer.py`: added `TemplateRenderer._add_other()`

---

<!-- entry:2026-10-02T23:28:47+05:30 -->
## 2026-10-02 23:28 (+0530) · P8.2, P8.4: content coverage check; phone numbers and portfolio links

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The ATS round-trip compared the rendered file with the parsed resume, so
> whatever the parser dropped was invisible: a German CV rendered as just a
> name and email still reported success. The new coverage check compares the
> output with the uploaded file's own lines. Rewrites, page-fit trims and the
> user's own edits or removals on Check details are counted apart; anything
> else missing fails the run and is named in a warning.
>
> It immediately found phone numbers lost in two of the eight generated
> cases, so the phone pattern (P8.4) is fixed in the same commit: any common
> grouping (US parentheses, +33 / +49 / +91 / +34 formats), never a year
> range or a date. Links now accept portfolio domains such as .design.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md
- Domain models: `M` app/domain/resume.py, `M` app/domain/resume_document.py
- Root: `M` app/eval/__main__.py, `M` app/eval/harness.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/integration/test_coverage_tailor.py, `M` tests/integration/test_persona_cases.py, `A` tests/unit/test_contact_p84.py, `A` tests/unit/test_coverage.py
- Tooling: `M` scripts/update_docs.py
- Validation: `A` app/validation/coverage.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer.find_phone()`
- `app/services/tailor.py`: added `TailorService._coverage()`
- new module `app/validation/coverage.py`: `class CoverageReport`

---

<!-- entry:2026-10-02T23:05:20+05:30 -->
## 2026-10-02 23:05 (+0530) · P8.1: persona eval cases from the cross-domain user test

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> All earlier eval cases were tech roles, so none of the user test's silent
> data loss could show up in the eval. The 22 personas (nurse, trades,
> lawyer, academic, EU / Indian / German / Spanish CVs, federal, text-box
> layout...) are now eval cases with hand-written ground truth: contact
> details including the phone, each job's title / company / dates / bullet
> count, education count, and phrases that must reach the rendered file.
>
> Each persona runs offline twice (content checks only, and every check).
> All 22 start as strict xfails naming the item meant to fix them, so every
> Phase 8 fix shows up as a case leaving the list.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Root: `M` app/eval/harness.py, `A` data/eval/personas/academic/expected.json, `A` data/eval/personas/academic/jd.txt, `A` data/eval/personas/academic/resume.docx, `A` data/eval/personas/accountant/expected.json, `A` data/eval/personas/accountant/jd.txt, `A` data/eval/personas/accountant/resume.docx, `A` data/eval/personas/designer/expected.json, `A` data/eval/personas/designer/jd.txt, `A` data/eval/personas/designer/resume.docx, `A` data/eval/personas/electrician/expected.json, `A` data/eval/personas/electrician/jd.txt, `A` data/eval/personas/electrician/resume.docx, `A` data/eval/personas/eu_cv/expected.json, `A` data/eval/personas/eu_cv/jd.txt, `A` data/eval/personas/eu_cv/resume.docx, `A` data/eval/personas/eu_en/expected.json, `A` data/eval/personas/eu_en/jd.txt, `A` data/eval/personas/eu_en/resume.docx, `A` data/eval/personas/executive/expected.json, `A` data/eval/personas/executive/jd.txt, `A` data/eval/personas/executive/resume.docx, `A` data/eval/personas/federal/expected.json, `A` data/eval/personas/federal/jd.txt, `A` data/eval/personas/federal/resume.docx, `A` data/eval/personas/gap/expected.json, `A` data/eval/personas/gap/jd.txt, `A` data/eval/personas/gap/resume.docx, `A` data/eval/personas/india/expected.json, `A` data/eval/personas/india/jd.txt, `A` data/eval/personas/india/resume.docx, `A` data/eval/personas/lawyer/expected.json, `A` data/eval/personas/lawyer/jd.txt, `A` data/eval/personas/lawyer/resume.docx, `A` data/eval/personas/manifest.json, `A` data/eval/personas/newgrad/expected.json, `A` data/eval/personas/newgrad/jd.txt, `A` data/eval/personas/newgrad/resume.docx, `A` data/eval/personas/nurse-pdf/expected.json, `A` data/eval/personas/nurse-pdf/jd.txt, `A` data/eval/personas/nurse-pdf/resume.pdf, `A` data/eval/personas/nurse/expected.json, `A` data/eval/personas/nurse/jd.txt, `A` data/eval/personas/nurse/resume.docx, `A` data/eval/personas/retail/expected.json, `A` data/eval/personas/retail/jd.txt, `A` data/eval/personas/retail/resume.docx, `A` data/eval/personas/sales-pdf/expected.json, `A` data/eval/personas/sales-pdf/jd.txt, `A` data/eval/personas/sales-pdf/resume.pdf, `A` data/eval/personas/sales/expected.json, `A` data/eval/personas/sales/jd.txt, `A` data/eval/personas/sales/resume.docx, `A` data/eval/personas/spanish/expected.json, `A` data/eval/personas/spanish/jd.txt, `A` data/eval/personas/spanish/resume.docx, `A` data/eval/personas/teacher/expected.json, `A` data/eval/personas/teacher/jd.txt, `A` data/eval/personas/teacher/resume.docx, `A` data/eval/personas/textbox/expected.json, `A` data/eval/personas/textbox/jd.txt, `A` data/eval/personas/textbox/resume.docx, `A` data/eval/personas/veteran/expected.json, `A` data/eval/personas/veteran/jd.txt, `A` data/eval/personas/veteran/resume.docx, `A` data/eval/personas/warehouse/expected.json, `A` data/eval/personas/warehouse/jd.txt, `A` data/eval/personas/warehouse/resume.docx
- Tests: `M` tests/integration/test_eval_cases.py, `A` tests/integration/test_persona_cases.py
- Tooling: `A` scripts/make_persona_cases.py

**Structure delta**

- `app/eval/harness.py`: added `_same_text()`, `check_job_details()`, `check_must_keep()`, `is_content_failure()`
- new module `scripts/make_persona_cases.py`

---

<!-- entry:2026-10-02T19:35:28+05:30 -->
## 2026-10-02 19:35 (+0530) · P7.1, P7.2: Review fixes: hyphenated terms, -ing fields, focus, job limits

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review of the first P7 commit found a matcher regression
> and a few gaps a user would hit. Stemming the whole hyphenated token cut
> the suffix before the term-suffix check, so "AWS-certified" and
> "cloud-native" no longer counted for AWS and cloud; each part is stemmed
> now. Folding -ing made "Marketing" match "market share" and "Accounting"
> match "key accounts", inflating the match and letting a new-job polish
> write those words in; fields named by an -ing word stay whole.
>
> On the details form, focus now follows Remove / Undo instead of dropping to
> the page, errors number new jobs as the cards show them, more than six
> lines is refused up front instead of silently trimmed, and the server
> refuses removing every job. On Results, when review asks no questions the
> button opens the own-words box rather than the top of the page.

**Changed files**

- Analysis: `M` app/analysis/keyword_match.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Root: `M` web/src/App.test.tsx, `M` web/src/lib/store.ts, `M` web/src/pages/Details.tsx, `M` web/src/pages/Results.test.tsx, `M` web/src/pages/Results.tsx, `M` web/src/pages/Review.tsx
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_check_parsed_resume.py, `M` tests/unit/test_keyword_match.py

---

<!-- entry:2026-10-02T18:47:51+05:30 -->
## 2026-10-02 18:47 (+0530) · P7.1, P7.2: Add/remove jobs on Check details; Results says what would move the match

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> From the owner's walk through the app as a user. "Check your details" showed
> the jobs read from the file with no way to add one the parser missed, so a
> missing job could only come in at the bottom of Review, after drafting, where
> it wasn't tailored or scored. Now each job can be removed (with Undo) and
> "Add a job we missed" adds new ones before drafting: the user's lines become
> bullets verbatim with matching evidence, so the draft step proposes rewrites
> for them and the match counts them. /api/proposals returns the corrected
> details, so going back doesn't add the job twice.
>
> Results showed "36% -> 36%" with one sentence pointing back to review. The
> score sheet now lists the keywords still missing (required first) with a
> button that opens Review at "What the job asks for", and names keywords that
> tailoring did add. Looking at the owner's run also found a matcher bug: the
> stemmer only removed plurals, so "Communicate" in the JD missed
> "Communicated" on the resume. Verb forms now fold too (36.4% -> 39.0% on
> that run), with short stems left whole so "string" and "spring" keep their
> meaning. Rewrites still never add a skill the resume doesn't show.

**Changed files**

- Analysis: `M` app/analysis/keyword_match.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Root: `M` web/src/App.test.tsx, `M` web/src/lib/api.ts, `M` web/src/lib/review.ts, `M` web/src/lib/store.ts, `M` web/src/lib/types.ts, `M` web/src/pages/Details.tsx, `M` web/src/pages/Results.test.tsx, `M` web/src/pages/Results.tsx, `M` web/src/pages/Review.tsx
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_api.py, `M` tests/unit/test_check_parsed_resume.py, `M` tests/unit/test_keyword_match.py
- Web API: `M` app/api/routes.py

**Structure delta**

- `app/services/tailor.py`: added `TailorService._insert_by_date()`, `TailorService._new_experience()`

---

<!-- entry:2026-10-01T20:23:57+05:30 -->
## 2026-10-01 20:23 (+0530) · P5.6: Parity check passed; remove the Streamlit UI

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The new web app now replaces Streamlit. Before removing it, the same
> proposals and choices were applied on the real resume (private, not
> committed) through the web API and through the Streamlit page's own
> argument building: identical DOCX text, match rate and PDF output, both
> for "accept everything" and for "reject one, edit one, tick a question".
>
> Removed: app/ui.py, the streamlit dependency, the Streamlit AppTest tests
> (the same behaviour is covered by the web flow tests and test_api.py),
> and the HTML/emoji review helpers only that page used (diff_html,
> status_badge; the diff tests now cover diff_spans). README, BUILD,
> PROJECT_OVERVIEW and the docs generator describe the web app instead.
> The "forget saved answers" button goes too: web visitors' answers only
> live in their own session.

**Changed files**

- Config: `M` app/config/settings.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Rendering: `M` app/rendering/review_view.py
- Root: `M` BUILD.md, `M` README.md, `D` app/ui.py, `M` pyproject.toml, `M` web/src/lib/review.ts
- Tests: `M` tests/unit/test_api.py, `M` tests/unit/test_check_parsed_resume.py, `M` tests/unit/test_gap_questions.py, `M` tests/unit/test_keyword_match.py, `M` tests/unit/test_new_role.py, `M` tests/unit/test_profile_store.py, `M` tests/unit/test_review_view.py, `M` tests/unit/test_tailor_resume_flow.py, `D` tests/unit/test_ui.py
- Tooling: `M` scripts/update_docs.py
- Web API: `M` app/api/forms.py, `M` app/api/sessions.py

**Structure delta**

- `app/rendering/review_view.py`: removed `_escape()`, `_render()`, `diff_html()`, `status_badge()`
- removed module `app/ui.py`

---

<!-- entry:2026-10-01T20:09:14+05:30 -->
## 2026-10-01 20:09 (+0530) · P5.5: Results screen with downloads, preview, change log and checks

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Completes the flow in the new UI: after generating, the visitor sees how
> the match moved, downloads the files, previews the exact PDF and reads
> what changed.
>
> - Before -> after keyword match with the verdict, PDF/DOCX downloads,
>   stat tiles, and tabs for the page preview, the change log (a small
>   safe Markdown renderer for changes.md, tables included), content
>   checks, notes and file checks. Back to review regenerates.
> - tailor_resume now returns `applied`: the bullets really rewritten, how
>   many are the user's own wording, and whether strict mode withheld
>   everything, so the summary describes the files, not the UI's guess.
>
> Independent review fixes: the rewritten count could be wrong under
> strict mode or after changing choices; a failed regenerate left old
> results reachable with dead downloads; downloads after session expiry
> saved an error page; the change log's table and nested lists were raw
> text; content notes sat under "File checks"; strict-mode withholding is
> now stated up front; phone sizing and rounding of the score.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Root: `A` web/src/components/MiniMarkdown.tsx, `M` web/src/lib/api.ts, `M` web/src/lib/types.ts, `A` web/src/pages/Results.test.tsx, `M` web/src/pages/Results.tsx, `M` web/src/pages/Review.tsx
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_tailor_resume_flow.py
- Web API: `M` app/api/routes.py

---

<!-- entry:2026-10-01T19:51:20+05:30 -->
## 2026-10-01 19:51 (+0530) · P5.3: Wire upload, check details, drafting and the match report to the API

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The new web UI now runs the first half of the flow against the real
> backend, so the Streamlit page is no longer needed to get to review.
>
> - Upload -> POST /api/parse -> "Check your details" (name, contact,
>   links, each job's company, titles and dates) -> POST /api/proposals,
>   streamed with live progress -> review step.
> - "Just check my match" -> POST /api/analyze -> a report page: score
>   dial against the target band, keywords found/missing by kind, where the
>   points come from, and each JD requirement; it can go straight on to
>   tailoring with the same file.
> - A fetch-based SSE reader (EventSource can't POST) and typed endpoints.
>   The run is kept in memory only; resumes never go to browser storage.
>
> Independent review fixes: a step finishing after the user left could
> pull them back into the old run (now aborted and ignored, stepper locked
> while running); Start over during a step silently failed to clear the
> server (it now resets when the step ends); drafting again lost earlier
> header fixes; an untouched form could erase a title-less role's dates;
> a new upload left stale steps reachable; the report's "similar wording"
> percentage was misleading; focus and tab keyboard handling.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Root: `M` web/package-lock.json, `M` web/package.json, `A` web/src/App.test.tsx, `M` web/src/App.tsx, `A` web/src/components/Field.tsx, `A` web/src/components/KeywordList.tsx, `A` web/src/components/ProgressPanel.tsx, `A` web/src/components/ScoreDial.tsx, `M` web/src/components/SettingsPopover.test.tsx, `M` web/src/components/Stepper.tsx, `M` web/src/components/UploadForm.tsx, `A` web/src/lib/api.test.ts, `M` web/src/lib/api.ts, `A` web/src/lib/inflight.ts, `A` web/src/lib/review.ts, `M` web/src/lib/store.ts, `A` web/src/lib/types.ts, `A` web/src/lib/useFocusHeading.ts, `A` web/src/pages/Details.tsx, `M` web/src/pages/Landing.tsx, `A` web/src/pages/Report.tsx, `A` web/src/pages/Review.tsx, `A` web/src/test/fixtures.ts, `M` web/src/test/setup.ts
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_api.py, `M` tests/unit/test_check_parsed_resume.py
- Web API: `M` app/api/routes.py, `M` app/api/sessions.py

---

<!-- entry:2026-10-01T19:22:37+05:30 -->
## 2026-10-01 19:22 (+0530) · P5.1: Web API layer (FastAPI) for the new public UI

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The tool will be hosted publicly, and Streamlit keeps every visitor's
> state in one process and reruns the whole page per click. This adds a
> FastAPI backend that the React UI (P5.2+) will call, wrapping
> TailorService unchanged.
>
> - app/api/routes.py: one endpoint per step (analyze, parse, proposals,
>   match-preview, tailor, files, preview, reset). The two long steps
>   stream progress as Server-Sent Events, ending in one result or error.
> - app/api/sessions.py: in-memory sessions behind a random httpOnly
>   cookie, idle expiry that deletes the visitor's temp files, and a lock
>   so one visitor's steps can't overlap.
> - Uploads checked by extension, magic bytes and size; LLM-costing steps
>   rate-limited per IP; model and target ids validated.
> - app/api/forms.py: the review-form logic that was inline in app/ui.py
>   (applied edits, which gap answers count, new-role checks, model
>   options). Streamlit now uses the same code, so the two UIs can't drift.
> - review_view gains diff_spans / proposal_state so the web client gets
>   the diff and status as data instead of HTML.
>
> Independent review fixes: a failure before the worker started left the
> session locked forever; the shared on-disk saved-answers profile would
> have leaked one visitor's answers to another (now one in-memory profile
> per session); worker errors are logged and shown generically; the
> cookie lifetime refreshes on activity; a failed first upload no longer
> orphans a session; a new run detaches downloads before deleting files.
> The remaining hosting hardening is tracked under P5.7.

**Changed files**

- Config: `M` app/config/settings.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/ui.py
- Rendering: `M` app/rendering/pdf_converter.py, `M` app/rendering/review_view.py
- Root: `M` BUILD.md, `M` pyproject.toml
- Services: `M` app/services/profile_store.py
- Tests: `A` tests/unit/test_api.py, `M` tests/unit/test_review_view.py
- Tooling: `M` scripts/update_docs.py
- Web API: `A` app/api/__init__.py, `A` app/api/forms.py, `A` app/api/main.py, `A` app/api/routes.py, `A` app/api/sessions.py

**Structure delta**

- new module `app/api/__init__.py`
- new module `app/api/forms.py`
- new module `app/api/main.py`
- new module `app/api/routes.py`: `class AdditionIn`, `class GapInput`, `class MatchPreviewIn`, `class NewRoleIn`, `class ProposalsIn`, `class RateLimiter`, `class SelectionItem`, `class TailorIn`
- new module `app/api/sessions.py`: `class Session`, `class SessionStore`
- `app/rendering/pdf_converter.py`: added `pdf_page_images()`
- `app/rendering/review_view.py`: added `_diff()`, `diff_spans()`, `proposal_state()`
- `app/services/profile_store.py`: added `MemoryProfileStore.__init__()`, `MemoryProfileStore.load()`, `MemoryProfileStore.save()`, `class MemoryProfileStore`
- `app/ui.py`: removed `model_options()`, `pdf_page_images()`

---

<!-- entry:2026-10-01T15:23:07+05:30 -->
## 2026-10-01 15:23 (+0530) · P4.3: Review fixes (education location, pairwise answer parsing, replay file)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review found:
> - The education fix covered only the degree line. An "Institution<tab>dates"
>   line still stored the dates as the location, and that hid the real city
>   on the next line. Both branches now refuse the date column as a location.
> - The judge's pairwise answer was compared literally, so "Resume A" or
>   "A." counted as a tie, quietly pushing verdicts towards "inconsistent".
>   The answer is now normalised.
> - `--replay` took the alphabetically first .docx, so a reused output
>   folder could have an older run's file judged. It now takes the newest
>   and warns when there are several.
> - Line breaks inside judge claims or errors broke the report's bullets.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Root: `M` app/eval/harness.py, `M` app/eval/judge.py
- Tests: `M` tests/unit/test_ats_round_trip.py, `M` tests/unit/test_judge.py

**Structure delta**

- `app/eval/judge.py`: added `_one_line()`

---

<!-- entry:2026-10-01T15:18:23+05:30 -->
## 2026-10-01 15:18 (+0530) · P4.3: LLM-as-judge from another model family, with position-swapped pairwise

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The harness measured structure (parse, keywords, pages, round-trip) but
> nothing judged whether a tailored resume actually reads better for the
> JD. A judge model from a different family than the generator (Qwen on
> Groq's free tier; the generator is gpt-oss), so it isn't grading its own
> writing, now scores each tailored resume:
> - a 1-5 rubric for relevance, clarity, faithfulness to the original, ATS
>   readability and overall, plus any claims the original doesn't support;
> - original vs tailored, asked twice with the positions swapped. The
>   tailored version only counts as better when it wins both, which cancels
>   the judge's position bias.
>
> `--judge` judges during a live run. `--replay DIR` judges outputs a
> previous run saved, without spending generator tokens. Each judged run
> writes a dated markdown report to the gitignored private reports folder.
> A failed judge call is reported rather than raised, and <think> blocks
> from reasoning models are stripped before parsing.
>
> The first live judging already paid off: its "date listed twice" remark
> on a test case exposed a parser bug, where an education line's date column
> was also stored as its location. That's fixed, and the ATS round-trip now
> compares education locations so it would catch it.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Config: `M` app/config/settings.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- LLM: `M` app/llm/client.py, `M` app/llm/prompts/final_review.txt, `A` app/llm/prompts/judge_pairwise.txt, `M` app/llm/schemas.py
- Root: `M` app/eval/__main__.py, `M` app/eval/harness.py, `A` app/eval/judge.py
- Tests: `M` tests/unit/test_ats_round_trip.py, `A` tests/unit/test_judge.py
- Tooling: `M` scripts/update_docs.py
- Validation: `M` app/validation/output.py

**Structure delta**

- `app/eval/harness.py`: added `_judge()`, `_judge_summary()`, `replay_case()`
- new module `app/eval/judge.py`: `class ResumeJudge`
- `app/llm/schemas.py`: added `class JudgePairwise`, `class JudgeRubric`

---

<!-- entry:2026-10-01T14:24:58+05:30 -->
## 2026-10-01 14:24 (+0530) · P1.4, P2.5: Retry Groq strict-JSON failures; rejoin hyphen-wrapped PDF lines

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The first live gate run since Stage C lost every bullet rewrite: Groq
> answered the role call with "json_validate_failed" and an empty
> generation, and the strict-schema path raised on any error instead of
> retrying. That error is transient, so it now gets the same retries as
> invalid JSON. The re-run rewrote all 12 proposals (Stage C: 9).
>
> The same run's ATS round-trip caught a PDF parsing bug: a line that wraps
> after the hyphen of a compound ("end-to-" / "end analytics") was rejoined
> with a space, giving "end-to- end". It now rejoins without one.
>
> Also: run folders saved rewrites.json as Python repr strings (lists of
> models went through str()), so they're written as JSON now. The eval no
> longer counts the summary's computed "4+ years" as a fabricated number.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md
- Ingestion: `M` app/ingestion/pdf.py
- LLM: `M` app/llm/client.py
- Root: `M` app/eval/harness.py
- Services: `M` app/services/run_manager.py
- Tests: `M` tests/unit/test_llm_client.py, `M` tests/unit/test_pdf_parser.py, `M` tests/unit/test_validation.py

**Structure delta**

- `app/ingestion/pdf.py`: added `_join_wrapped()`

---

<!-- entry:2026-10-01T00:32:06+05:30 -->
## 2026-10-01 00:32 (+0530) · P4.2: Second review fixes (school-word headings, pipe locations, PDF columns)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The re-review confirmed the first round of fixes, and found that they
> introduced two regressions of their own plus three smaller issues:
> - Headings like "University Projects" and "College Activities" stopped
>   starting a section. A heading is now treated as content only when its
>   sole keywords are technology or university and it names an
>   institution.
> - "Software Engineer | Google | Mountain View" took the location as the
>   company. With pipes, the company is the first segment that isn't the
>   title. With dashes only, it's the last part ("Analyst — Payments Team
>   — Acme Corp" -> Acme Corp).
> - A lone date inside a two-column PDF's right column could still be
>   attached to a left-column line. A mid-page column now also needs a line
>   starting at the left margin that runs across it, which only happens on
>   a single-column page.
> - A bold header row of a skills table ("Languages | Tools") was merged.
> - "react quickly" and "use git" still produced keywords.
> Each case is pinned in test_parser_regressions_p42.py.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py, `M` app/analysis/terminology.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Ingestion: `M` app/ingestion/docx.py, `M` app/ingestion/pdf.py
- Tests: `M` tests/unit/test_parser_regressions_p42.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._split_title_company()`

---

<!-- entry:2026-10-01T00:24:21+05:30 -->
## 2026-10-01 00:24 (+0530) · P4.2: Review fixes (narrow the parser changes that broke other inputs)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review failed the first P4.2 commit. Its parser fixes
> made the eval cases pass but broke common inputs outside the set. Each
> fix is now narrowed, and every reproducing input is a regression test:
> - Section headings: an allowlist of title words stopped "Internship
>   Experience", "Programming Skills", "Licenses & Certifications" and
>   similar from starting a section, so whole resumes collapsed into
>   Education. A heading with a section keyword switches again, unless it
>   reads as content (a school or company name, or a long line).
> - Skills tables: any two-cell row was merged as "Label: values", which
>   lost side-by-side skills ("Python | SQL, Excel"). Now only rows whose
>   first cell is a label (bold, "Label:", or a known category) merge.
> - PDF columns: any date or "City, Country" run mid-page was attached,
>   which stitched two-column pages together. Now a run is attached only
>   when everything printed at that x is a date or a place.
> - Keyword matching split every hyphenated word, so Go matched
>   go-to-market and R matched R-squared. It now splits only before
>   suffixes like -compliant or -certified.
> - The always-keep tech vocabulary included English words, so "the rest
>   of the team" produced REST. Those words now need the capitalisation
>   rule.
> Also: when both sides of "A | B" contain a role word, the part ending in
> one is the title ("Data Analyst | Lead Bank"), and the fabricated-number
> check compares units and reads table cells.

**Changed files**

- Analysis: `M` app/analysis/keyword_match.py, `M` app/analysis/resume_normalizer.py, `M` app/analysis/terminology.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Ingestion: `M` app/ingestion/docx.py, `M` app/ingestion/pdf.py
- Root: `M` app/eval/harness.py
- Tests: `M` tests/integration/test_eval_cases.py, `A` tests/unit/test_parser_regressions_p42.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._title_score()`
- `app/eval/harness.py`: added `_norm_number()`

---

<!-- entry:2026-10-01T00:10:22+05:30 -->
## 2026-10-01 00:10 (+0530) · P4.2: Anonymized evaluation set with expected facts, and the gaps it found

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Three cases couldn't show whether parsing, keyword analysis and output
> hold up across the resumes people actually have. scripts/make_eval_cases.py
> now writes 8 more anonymized pairs (fictional people and companies) from
> ground truth: new graduate, 12-year senior, career changer, table-layout
> DOCX, promotion with sub-projects, PDF, a JD buried in boilerplate, and a
> product manager. Each has an expected.json derived from the same truth, so
> the eval checks what's really in the file, not what the parser happens to
> read.
>
> The harness adds attainable keyword coverage (of the JD keywords the resume
> plainly contains, the share the matcher finds; target >= 95%), numbers in
> the output that the resume never had, a keyword-stuffing guard (tailoring
> pushing the rate over the band, or a keyword repeated more than 5 times),
> and pass/fail against expected.json. `--check` exits 1 on any miss, and
> `pytest -m eval` runs the whole set offline.
>
> The first run failed 7 of 8 cases. The gaps are real ones that affect
> uploaded resumes, fixed here:
> - "PROJECTS" never started a section (only the singular keyword existed),
>   so projects were folded into the last job.
> - Any heading containing a keyword switched section, e.g. "Riverside
>   Institute of Technology" moved education into skills. A heading must
>   now be made of section-like words.
> - "Title | Company | dates" kept the company inside the title.
> - Skills tables read the category cells as skills.
> - PDF dates and places at a mid-page tab stop weren't attached to their
>   line.
> - "Certificate" and "B.Ed." weren't degrees.
> - "HIPAA-compliant" didn't count as HIPAA.
> - The offline JD analysis dropped sentence-initial or lowercase tools
>   (Python, pytest, dbt), which the new TECH_TERMS vocabulary keeps, and
>   bare "A/B" beat "A/B testing".
> All 11 cases now pass, and the user's resume still matches its golden
> parse.

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py, `M` app/analysis/keyword_match.py, `M` app/analysis/resume_normalizer.py, `M` app/analysis/terminology.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Ingestion: `M` app/ingestion/docx.py, `M` app/ingestion/pdf.py
- Root: `M` CLAUDE.md, `M` app/eval/__main__.py, `M` app/eval/harness.py, `A` data/eval/cases/boilerplate-jd/expected.json, `A` data/eval/cases/boilerplate-jd/jd.txt, `A` data/eval/cases/boilerplate-jd/resume.docx, `A` data/eval/cases/career-changer/expected.json, `A` data/eval/cases/career-changer/jd.txt, `A` data/eval/cases/career-changer/resume.docx, `A` data/eval/cases/manifest.json, `A` data/eval/cases/new-grad/expected.json, `A` data/eval/cases/new-grad/jd.txt, `A` data/eval/cases/new-grad/resume.docx, `A` data/eval/cases/pdf-mid/expected.json, `A` data/eval/cases/pdf-mid/jd.txt, `A` data/eval/cases/pdf-mid/resume.pdf, `A` data/eval/cases/product-manager/expected.json, `A` data/eval/cases/product-manager/jd.txt, `A` data/eval/cases/product-manager/resume.docx, `A` data/eval/cases/promotion-projects/expected.json, `A` data/eval/cases/promotion-projects/jd.txt, `A` data/eval/cases/promotion-projects/resume.docx, `A` data/eval/cases/senior-12y/expected.json, `A` data/eval/cases/senior-12y/jd.txt, `A` data/eval/cases/senior-12y/resume.docx, `A` data/eval/cases/table-docx/expected.json, `A` data/eval/cases/table-docx/jd.txt, `A` data/eval/cases/table-docx/resume.docx, `M` pyproject.toml
- Tests: `A` tests/integration/test_eval_cases.py, `M` tests/unit/test_eval_harness.py, `M` tests/unit/test_jd_analyzer_v2.py
- Tooling: `A` scripts/make_eval_cases.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._is_section_title()`, `ResumeNormalizer._looks_like_title()`
- `app/eval/harness.py`: added `_docx_text()`, `attainable_coverage()`, `check_expected()`, `fabricated_numbers()`, `stuffing()`
- `app/ingestion/docx.py`: added `DocxParser._skills_label_row()`
- new module `scripts/make_eval_cases.py`

---

<!-- entry:2026-09-30T23:54:15+05:30 -->
## 2026-09-30 23:54 (+0530) · P3.6: Review fixes (CLI follows the UI's confirm rules, clean errors)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review found the proposals file bypassing the rules the
> review screen enforces:
> - Emptying confirmed_keywords left a pre-filled saved answer in place,
>   and it was still turned into a bullet. As in the UI, an unchanged saved
>   answer now counts only while one of its keywords is listed. The file
>   marks what was pre-filled from earlier applications, and the help text
>   says to remove what doesn't apply.
> - Gap questions weren't passed on, so facts saved from the CLI lost the
>   JD line they came from.
> - model_dump's legacy mirror keys (rewritten_text, ...) were written into
>   the file as a second copy of the text, where an edit was ignored.
>
> Bad input now fails before any work, with "Error: ..." instead of a
> traceback: missing or invalid JSON, and an invalid new job
> (validate_new_role() is shared with add_new_role()). Only an explicit
> "apply": true applies a proposal (the string "false" used to count as
> yes), and a file from an older schema has its JD analysed again instead of
> crashing.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/cli.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_cli_parity.py

**Structure delta**

- `app/cli.py`: added `_without_mirrors()`
- `app/services/tailor.py`: added `TailorService.validate_new_role()`

---

<!-- entry:2026-09-30T23:49:04+05:30 -->
## 2026-09-30 23:49 (+0530) · P3.6: Live progress in the UI and a CLI with the UI's features

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> A run showed one spinner for up to a minute, so the user couldn't tell
> parsing from rewriting or a slow Groq call (F31). generate_proposals()
> and tailor_resume() now report each step through an optional callback,
> guarded so a failing reporter can never break a run. The UI shows the
> steps live in st.status boxes and the CLI prints them.
>
> The CLI could only analyze and tailor blindly: no review, no edits, no gap
> answers, additions or new job. `propose` now writes an editable JSON file
> with everything the review screen offers, and `tailor --proposals FILE`
> applies exactly that, with the same rules as the UI (edits are
> user-attested, rejected rewrites start unticked). The file also carries
> the JD analysis so tailoring doesn't pay for it twice on the free tier.
> --strict and --no-remember mirror the UI toggles, and the CLI now reports
> the keyword match rate instead of the retired "/ 100" score.

**Changed files**

- Analysis: `M` app/analysis/rewriter.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/cli.py, `M` app/ui.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_cli_parity.py

**Structure delta**

- `app/cli.py`: added `_print_progress()`, `read_proposals()`, `write_proposals()`
- `app/services/tailor.py`: added `_progress()`

---

<!-- entry:2026-09-30T23:46:55+05:30 -->
## 2026-09-30 23:46 (+0530) · P3.2: Review fixes (withdrawing pre-filled answers, profile robustness)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review found a hole in suggest-and-confirm: a saved answer
> is pre-filled into the text box, so unticking every keyword (as the
> caption tells the user to) still submitted the answer, and it became a
> bullet. An unchanged pre-filled answer now counts only while one of its
> keywords is ticked. A pre-filled answer is also no longer copied onto
> other keywords ticked next to it, which would have attached one skill's
> story to another on the next JD.
>
> load() treated any error as corruption and renamed the file, so a
> permissions problem (or a folder at that path) moved a good profile
> aside. Only unparseable content is set aside now. An unreadable file is
> left alone, Forget can't crash the page, forgetting an empty profile
> writes nothing, the default path is absolute under the repo, and Start
> Over clears the gap-question widgets so a new JD's "gap_1" can't inherit
> old ticks.

**Changed files**

- Config: `M` app/config/settings.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/ui.py
- Services: `M` app/services/profile_store.py
- Tests: `M` tests/unit/test_profile_store.py

---

<!-- entry:2026-09-30T23:41:58+05:30 -->
## 2026-09-30 23:41 (+0530) · P3.2: Remember confirmed gap answers and pre-fill them on the next JD

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Every JD asked the same gap questions again ("have you used Kafka?"),
> even when the user had answered them for the previous application. The
> agreed decision is that confirmed facts are saved locally and reused.
>
> ProfileStore keeps them in data/profile/facts.json (gitignored, never
> sent anywhere): the keyword as the JD spelled it, the user's answer, the
> JD line it came from and when. The next JD's matching questions come up
> already ticked with the saved answer and a note saying so. That keeps the
> suggest-and-confirm rule: the user still sees and keeps each one for this
> JD, and nothing is added silently. Writes are atomic, a damaged file is
> set aside rather than blocking a run, and the sidebar can turn saving off
> or forget everything. Tests are pinned to a temporary profile so they can
> never read or write the real one.

**Changed files**

- Analysis: `M` app/analysis/gap_questions.py
- Config: `M` app/config/settings.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/ui.py
- Root: `M` .gitignore
- Services: `A` app/services/profile_store.py, `M` app/services/tailor.py
- Tests: `M` tests/conftest.py, `A` tests/unit/test_profile_store.py
- Tooling: `M` scripts/update_docs.py

**Structure delta**

- new module `app/services/profile_store.py`: `class ConfirmedFact`, `class Profile`, `class ProfileStore`
- `app/services/tailor.py`: added `TailorService._prefill_from_profile()`

---

<!-- entry:2026-09-30T23:38:42+05:30 -->
## 2026-09-30 23:38 (+0530) · P3.3: Review fixes (require dates and a description, whole-word keywords)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review ran real tailoring with new jobs and found that a
> job without a start date, without an end date, or without any bullets
> comes out of the ATS round-trip wrong; with no bullets, the parser even
> merged it into the next job and misread that job's company and dates. A
> new job now needs company, title, start date, an end date or "I currently
> work here", and at least one description line, and the end can't be
> before the start. This is checked in add_new_role() and in the form,
> which lists what's missing instead of silently dropping a partly filled
> job.
>
> Also from the review: JD keywords offered to the polish are matched as
> whole words (a plain substring check offered "R" for "Reduced" and "Go"
> for "go-to-market", which got good polishes discarded by the fact check),
> "today" / "ongoing" count as current like everywhere else, and every
> ongoing job keeps page-fit's 3-bullet minimum, not just the first one.

**Changed files**

- Analysis: `M` app/analysis/experience.py
- Docs: `M` docs/ACTION_ITEMS.md
- Entry points: `M` app/ui.py
- Rendering: `M` app/rendering/page_fit.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_new_role.py

**Structure delta**

- `app/analysis/experience.py`: added `is_ongoing()`
- `app/rendering/page_fit.py`: added `_is_current()`

---

<!-- entry:2026-09-30T23:33:18+05:30 -->
## 2026-09-30 23:33 (+0530) · P3.3: Add a job that isn't on the resume

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> There was no way to add a job (F20): additions could only append one
> bullet to an existing role or create a generic project. The review form now
> has an "Add a job that isn't on your resume" section (company and title
> required, location, start/end month or "I currently work here", and a
> description in the user's own words).
>
> add_new_role() turns the description into at most 6 bullets. Each is
> polished with only the JD keywords already in it and fact-checked against
> the user's text, and the user's own wording is kept whenever the polish
> adds anything, the same rule as gap answers. The job is placed in date
> order, and PRESERVE output switches to the template because a new job has
> no place in the original file's layout.
>
> While wiring this in, the page-fit loop turned out to treat every bullet
> the user adds in a run (gap answers, additions, a new job) as zero
> relevance, because the planner never saw them, so they were the first to
> be trimmed. They now count as fully relevant.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/ui.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_new_role.py

**Structure delta**

- `app/services/tailor.py`: added `TailorService._fit_relevance()`, `TailorService._split_description()`, `TailorService.add_new_role()`

---

<!-- entry:2026-09-30T23:32:09+05:30 -->
## 2026-09-30 23:32 (+0530) · P3.4: Review fixes (Markdown in diffs, stale live rate, preview parity)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review of the review screen found three real bugs:
> - st.markdown still interprets Markdown and LaTeX inside the HTML diff, so
>   a bullet like "cut cost from $2M to $1M" rendered as math and "*" as
>   emphasis. Markdown characters are now numeric entities after escaping.
> - The "current selection" match rate survived Start Over and showed next
>   to a new run's proposals; it's cleared on Start Over and on new drafts.
> - The recalculated rate counted ticked rewrites the validator rejects,
>   which Apply drops unless the user edited them, so it overstated the
>   result. The preview now skips them like Apply does, applies only bullet
>   kinds as bullets, and a caption notes Strict Mode's all-or-nothing rule.
>
> Also from the review: ".NET" now highlights, and the skills diff keeps its
> line breaks instead of flattening into one paragraph.

**Changed files**

- Entry points: `M` app/ui.py
- Rendering: `M` app/rendering/review_view.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_review_view.py

**Structure delta**

- `app/rendering/review_view.py`: added `_escape()`

---

<!-- entry:2026-09-30T23:27:36+05:30 -->
## 2026-09-30 23:27 (+0530) · P3.4: Review screen with diff, badges, accept-all and live match rate

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Reviewing proposals meant reading two blocks of text and spotting the
> differences by eye, with separate captions for validation and call status,
> and the match rate only changed after a full Apply & Generate (F17, F31).
>
> Each proposal now shows one status badge (the thing to act on first), the
> original and the proposal side by side with removed and added words
> marked and JD keywords in bold, and the edit box. Accept all / Reject all
> set every checkbox. Because Streamlit forms only rerun on submit, a second
> submit button recalculates the match rate from the ticked, edited text
> (deterministic, no LLM, nothing rendered) and shows it next to the
> before-tailoring rate. A keyword-gap table lists what the JD asks for that
> the resume lacks and whether a question below covers it, and every
> keyword table now has a per-kind score breakdown that sums to the rate.
>
> The display logic lives in rendering/review_view.py as plain functions so
> it can be tested without Streamlit.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/ui.py
- Rendering: `A` app/rendering/review_view.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_keyword_match.py, `A` tests/unit/test_review_view.py
- Tooling: `M` scripts/update_docs.py

**Structure delta**

- new module `app/rendering/review_view.py`
- `app/services/tailor.py`: added `TailorService.preview_keyword_match()`

---

<!-- entry:2026-09-30T23:24:47+05:30 -->
## 2026-09-30 23:24 (+0530) · P1.10: Guard fixes from review (joiners, line separators, JD invisibles)

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The independent review of the guard found it could quietly damage
> non-English text: ZWNJ / ZWJ are needed by Devanagari and Persian, and
> U+2028/2029 were deleted rather than turned into line breaks. Plain "<s>"
> no longer counts as a chat token (only "</s>"), and list-style or empty
> message content is left alone instead of raising.
>
> JD text now loses invisible characters too, before analysis: the LLM saw
> the cleaned text while the verbatim check compared against the raw JD, so a
> skill written with a zero-width space inside it was silently dropped.

**Changed files**

- Tests: `M` tests/unit/test_validation.py
- Validation: `M` app/validation/safety.py

**Structure delta**

- `app/validation/safety.py`: added `SafetyGuard.strip_invisible()`

---

<!-- entry:2026-09-30T23:21:11+05:30 -->
## 2026-09-30 23:21 (+0530) · P1.10: Remove dead code and unused prompts; guard every LLM prompt

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> validation_agent.py was never imported and three prompt files had no
> callers (F32); keeping them made it unclear which prompts are live.
> final_review.txt stays for the LLM judge (P4.3).
>
> Only JD text was sanitised before reaching the LLM; resume text, user
> additions and gap answers went in raw (F35). Every call now passes through
> SafetyGuard.guard_messages() inside LLMClient, so no call site can forget
> it: user content loses invisible characters, chat-template tokens and
> explicit "ignore previous instructions" overrides, and each system prompt
> states that resume/JD text is data, not instructions. The resume filter is
> deliberately narrower than the JD one: an ML resume can legitimately say
> "designed system prompts", and rewriting that would corrupt the bullet.
>
> PROJECT_OVERVIEW's open-issues list is refreshed: the 2026-09-29 audit
> items were all fixed in Phase 0.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- LLM: `M` app/llm/client.py, `D` app/llm/prompts/resume_normalization.txt, `D` app/llm/prompts/tailoring_plan.txt, `D` app/llm/prompts/validate_claims.txt
- Services: `D` app/services/validation_agent.py
- Tests: `M` tests/unit/test_llm_client.py, `M` tests/unit/test_validation.py
- Tooling: `M` scripts/update_docs.py
- Validation: `M` app/validation/safety.py

**Structure delta**

- removed module `app/services/validation_agent.py`
- `app/validation/safety.py`: added `SafetyGuard.guard_messages()`, `SafetyGuard.sanitize_untrusted()`

---

<!-- entry:2026-09-30T22:42:38+05:30 -->
## 2026-09-30 22:42 (+0530) · P2.6: Content checks on the finished resume

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> There were no content-quality checks at all (F30), so a tailored resume
> could keep pronouns, clichés, present tense in past jobs or eight bullets
> under one role without the user being told. content_lint runs on the
> rendered resume without an LLM and reports bullets per role, bullet length,
> pronouns, buzzwords (sharing the rewrite prompt's filler list and 28-word
> limit so advice and rewrites agree), tense, repeated opening verbs, date
> problems and the share of bullets that carry a number.
>
> These are suggestions, not validation failures: nothing is changed
> automatically and the run's success isn't affected. They appear in a
> "Content checks" expander on the results screen, in changes.md and in the
> eval metrics. A company with a promotion gets room for more bullets, since
> two roles legitimately need more than one role's 3-6.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/ui.py
- Root: `M` app/eval/harness.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_content_lint.py, `M` tests/unit/test_ui.py
- Tooling: `M` scripts/update_docs.py
- Validation: `A` app/validation/content_lint.py

**Structure delta**

- `app/ui.py`: added `_show_content_checks()`
- new module `app/validation/content_lint.py`: `class ContentReport`, `class LintIssue`

---

<!-- entry:2026-09-30T22:38:42+05:30 -->
## 2026-09-30 22:38 (+0530) · P2.5: ATS round-trip QA on the rendered DOCX and PDF

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Output QA only checked that the files existed and contained the name
> (F29), so nothing proved an ATS could read back what we render. The
> template output is now re-parsed with our own parser (no LLM) and compared
> with the resume that was rendered: contact details, links, sections,
> companies, every role title and date, every bullet, skills and education.
> Any difference is a critical warning, so the run reports failure instead
> of shipping a file that parses wrong.
>
> Running it immediately found gaps in the parser that also affect real
> uploaded resumes, fixed here: dates in a right-aligned column were dropped,
> "Company · Location" wasn't split, a company line after the title line
> started a new job (or became a bullet), a degree-first education line was
> read as the institution, and a DOCX skills line with a bold "Tools:" label
> was taken for a section heading. All eval cases now round-trip cleanly.

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Ingestion: `M` app/ingestion/docx.py
- Root: `M` app/eval/harness.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_ats_round_trip.py
- Validation: `M` app/validation/output.py

**Structure delta**

- `app/analysis/resume_normalizer.py`: added `ResumeNormalizer._looks_like_degree()`, `ResumeNormalizer._split_middle_dot()`
- `app/validation/output.py`: added `OutputQAValidator.round_trip()`

---

<!-- entry:2026-09-30T22:30:41+05:30 -->
## 2026-09-30 22:30 (+0530) · P2.4: Page-fit loop trims the least relevant content to the page target

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Nothing counted pages (F27), so a 3.6-year resume came out at 2 pages
> against the 1-page rule. The template path now renders, converts to PDF,
> measures the overflow on the last page and removes content in the agreed
> order (Interests, least relevant bullets within per-role minimums, whole
> low-relevance sub-sections or projects, then compact spacing) until it
> fits. The overflow is converted into an estimated amount to trim so a
> typical run needs 2 LibreOffice renders instead of one per step; the
> render cap is 4.
>
> A lone low-relevance bullet under its own sub-heading is removed with its
> heading in the bullet step: ranking purely by relevance beats protecting a
> 0.01-relevance bullet while cutting a 0.7 one elsewhere.
>
> Content is only removed, never reworded, and every removal is logged in
> changes.md and shown as a warning; the keyword rate is recomputed after
> trimming so the reported score matches the rendered file.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Rendering: `A` app/rendering/page_fit.py, `M` app/rendering/template_renderer.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_page_fit.py, `M` tests/unit/test_tailor_resume_flow.py
- Tooling: `M` scripts/update_docs.py

**Structure delta**

- new module `app/rendering/page_fit.py`: `class FitResult`, `class PageFitter`
- `app/services/tailor.py`: added `TailorService._render_template()`

---

<!-- entry:2026-09-30T22:17:12+05:30 -->
## 2026-09-30 22:17 (+0530) · P2.3: Page target (1 or 2 A4 pages) from years of experience

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The years calculation already existed (P1.5, overlaps merged); the page
> target it feeds did not. target_pages() applies the fixed decision (one
> page under 8 years, two from 8 years) so the page-fit loop (P2.4) has a
> goal to trim towards. It's returned by tailor_resume() and recorded by the
> eval harness next to the actual page count, so the stage gate can compare
> the two directly.

**Changed files**

- Analysis: `M` app/analysis/experience.py
- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Root: `M` app/eval/harness.py
- Services: `M` app/services/tailor.py
- Tests: `A` tests/unit/test_experience.py

**Structure delta**

- `app/analysis/experience.py`: added `target_pages()`

---

<!-- entry:2026-09-30T22:15:59+05:30 -->
## 2026-09-30 22:15 (+0530) · P2.2: ATS template is the default output; PRESERVE moves to Advanced

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The UI defaulted to PRESERVE (F28), which patches text into the uploaded
> DOCX: it can't reorder bullets, trim to a page count or apply the new A4
> template, so most of Stage D would never reach a default run. The sidebar
> radio is replaced by an "Advanced" expander with an opt-in "Keep my
> original DOCX layout" checkbox that explains what it gives up. The service
> and CLI defaults switch to ATS_DEFAULT too, so every entry point behaves
> the same.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Entry points: `M` app/cli.py, `M` app/ui.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_ui.py

---

<!-- entry:2026-09-30T21:56:30+05:30 -->
## 2026-09-30 21:56 (+0530) · P2.1: ATS template spec in DOCX and HTML, driven by ResumePresentation

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The DOCX renderer ignored presentation.section_order (F26), used Letter
> and Calibri while the HTML preview used A4, and the two outputs named
> sections differently. The layout rules now live in one module
> (rendering/layout.py) that both renderers read, so the download and the
> preview can't drift apart again:
>
> - A4, 0.7" side / 0.6" top-bottom margins, Arial, single column, no tables
>   or Word header.
> - Standard section headings, rendered in presentation.section_order;
>   education moves before experience for someone with under 2 dated years
>   (or no jobs), per the fixed layout decision.
> - Dates written "Aug 2024 - Present" (en dash), the agreed India/Europe
>   format; wording the parser doesn't recognise is kept as written.
> - Contact line "email | phone | location | linkedin | github".
> - At most 4 skill lines; the overflow is merged into "Other" rather than
>   dropped.
> - Output files named First_Last_Resume_<Company>, also used for the UI
>   downloads.
>
> Page length is untouched here: trimming to the target page count is P2.4.

**Changed files**

- Docs: `M` docs/ACTION_ITEMS.md, `M` docs/PROJECT_OVERVIEW.md
- Domain models: `M` app/domain/resume_document.py
- Entry points: `M` app/ui.py
- Rendering: `M` app/rendering/html_renderer.py, `A` app/rendering/layout.py, `M` app/rendering/template_renderer.py
- Services: `M` app/services/tailor.py
- Tests: `M` tests/unit/test_html_renderer.py, `A` tests/unit/test_template_layout.py
- Tooling: `M` scripts/update_docs.py

**Structure delta**

- `app/rendering/html_renderer.py`: added `HtmlResumeRenderer._section()`
- new module `app/rendering/layout.py`
- `app/rendering/template_renderer.py`: added `TemplateRenderer._add_achievements()`, `TemplateRenderer._add_bullets()`, `TemplateRenderer._add_certifications()`, `TemplateRenderer._add_education()`, `TemplateRenderer._add_experience()`, `TemplateRenderer._add_header()`, `TemplateRenderer._add_interests()`, `TemplateRenderer._add_meta_line()`, `TemplateRenderer._add_projects()`, `TemplateRenderer._add_skills()`, `TemplateRenderer._add_summary()`

---

<!-- entry:2026-09-30T21:50:22+05:30 -->
## 2026-09-30 21:50 (+0530) · P1.4: Retry bullets returned unchanged that still break the rules

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> The Stage C re-run (no skipped bullets any more) showed the other half of
> the problem: the role call returned 6 of 12 bullets word-for-word, including
> ones over 28 words or containing "robust" / "seamless" / "dynamic", which
> the prompt says must not be kept as is. The same single follow-up call now
> also takes those bullets, with a note that they may not come back unchanged.
> The check is deterministic (word count + filler list), so a bullet that is
> already short and clean can still legitimately stay unchanged, and a retry
> only replaces a kept bullet when it actually changed it. Still at most one
> extra call per role.

**Changed files**

- Analysis: `M` app/analysis/rewriter.py
- Docs: `M` docs/ACTION_ITEMS.md
- Tests: `M` tests/unit/test_rewriter.py

**Structure delta**

- `app/analysis/rewriter.py`: added `breaks_bullet_rules()`

---

<!-- entry:2026-09-30T19:57:53+05:30 -->
## 2026-09-30 19:57 (+0530) · P1.4: Retry bullets a role call skipped; fail fast on long Groq limits

Kshitij Chaubey · branch `fb_ksh`

**Why / details**

> Two problems from the Stage C gate run on the real resume:
>
> 1. The per-role rewrite returned only 7 of 10 bullets; the last project's
>    three came back as llm_error. When a call returns some bullets but not
>    all, one follow-up call now asks for just the missing ones (at most one
>    extra call per role, so the budget holds).
>
> 2. After a day of development runs the free tier's daily token limit
>    (200K TPD for gpt-oss-120b) was hit. Groq said "try again in 15m43s",
>    but the client slept 3 x 30 s and failed anyway. When the requested
>    wait (retry-after header, or "try again in ...m...s" in the body) is
>    longer than GROQ_MAX_RETRY_WAIT, it now fails immediately with "Groq
>    free-tier daily token limit reached; try again in about 16 min", which
>    the UI banner and each proposal show.

**Changed files**

- Analysis: `M` app/analysis/rewriter.py
- LLM: `M` app/llm/client.py
- Tests: `M` tests/unit/test_llm_client.py, `M` tests/unit/test_rewriter.py

**Structure delta**

- `app/llm/client.py`: added `_requested_wait()`

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

<!-- entry:2026-08-31T16:11:26+05:30 -->
## 2026-08-31 16:11 (+0530) · Fix: resolve merge markers in TailorService return payload

`8f97080` · Kshitij Chaubey

**Changed files**

- Services: `M` app/services/tailor.py

**Structure delta**

- `app/services/tailor.py`: added `TailorService.__init__()`, `TailorService.analyze_only()`, `TailorService.generate_preview_md()`, `TailorService.tailor_resume()`, `class TailorService`

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

<!-- entry:2026-08-31T14:34:17+05:30 -->
## 2026-08-31 14:34 (+0530) · Phase1: wire StructuralValidator, enforce Strict Factual Mode from UI, include validation warnings in report

`6221d73` · Kshitij Chaubey

**Changed files**

- Entry points: `M` app/ui.py
- Services: `M` app/services/tailor.py

---

<!-- entry:2026-08-31T14:33:01+05:30 -->
## 2026-08-31 14:33 (+0530) · Phase1: wire StructuralValidator and OutputQAValidator into TailorService; collect validation warnings

`2261605` · Kshitij Chaubey

**Changed files**

- Services: `M` app/services/tailor.py

**Structure delta**

- `app/services/tailor.py`: removed `TailorService.__init__()`, `TailorService.analyze_only()`, `TailorService.generate_preview_md()`, `TailorService.tailor_resume()`, `class TailorService`

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

<!-- entry:2026-08-30T19:10:52+05:30 -->
## 2026-08-30 19:10 (+0530) · Render all canonical resume sections in ATS DOCX

`24b1435` · alwayss-snape

**Changed files**

- Rendering: `M` app/rendering/template_renderer.py

---

<!-- entry:2026-08-30T19:10:35+05:30 -->
## 2026-08-30 19:10 (+0530) · Patch the correct paragraph in table resume cells

`51762e1` · alwayss-snape

**Changed files**

- Rendering: `M` app/rendering/docx_patcher.py

---

<!-- entry:2026-08-30T19:10:27+05:30 -->
## 2026-08-30 19:10 (+0530) · Parse table cell paragraphs without flattening

`a4be27e` · alwayss-snape

**Changed files**

- Ingestion: `M` app/ingestion/docx.py

---

<!-- entry:2026-08-30T19:10:12+05:30 -->
## 2026-08-30 19:10 (+0530) · Track paragraph locations inside DOCX table cells

`83de8ba` · alwayss-snape

**Changed files**

- Rendering: `M` app/rendering/document_map.py

---

<!-- entry:2026-08-30T19:08:08+05:30 -->
## 2026-08-30 19:08 (+0530) · Use ATS HTML preview when PDF is unavailable

`cc02a1d` · alwayss-snape

**Changed files**

- Entry points: `M` app/ui.py

---

<!-- entry:2026-08-30T19:07:44+05:30 -->
## 2026-08-30 19:07 (+0530) · Render canonical resume as ATS HTML artifact

`5ecaa31` · alwayss-snape

**Changed files**

- Services: `M` app/services/tailor.py

---

<!-- entry:2026-08-30T19:07:20+05:30 -->
## 2026-08-30 19:07 (+0530) · Test ATS HTML resume rendering

`fe004d3` · alwayss-snape

**Changed files**

- Tests: `A` tests/unit/test_html_renderer.py

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

<!-- entry:2026-08-30T19:06:22+05:30 -->
## 2026-08-30 19:06 (+0530) · Expand canonical document contract coverage

`5d443d9` · alwayss-snape

**Changed files**

- Tests: `M` tests/unit/test_resume_document.py

---

<!-- entry:2026-08-30T19:04:11+05:30 -->
## 2026-08-30 19:04 (+0530) · Test canonical resume document contract

`959be1a` · alwayss-snape

**Changed files**

- Tests: `A` tests/unit/test_resume_document.py

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

<!-- entry:2026-08-29T21:20:23+05:30 -->
## 2026-08-29 21:20 (+0530) · Keep grounded validation test deterministic

`965792f` · alwayss-snape

**Changed files**

- Tests: `M` tests/unit/test_validation.py

---

<!-- entry:2026-08-29T21:20:12+05:30 -->
## 2026-08-29 21:20 (+0530) · Allow grammatical variants in claim validation

`1adf729` · alwayss-snape

**Changed files**

- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/validation/factual.py`: added `FactualValidator._canonical_term()`

---

<!-- entry:2026-08-29T21:20:01+05:30 -->
## 2026-08-29 21:20 (+0530) · Test rejection of fabricated resume claims

`f5cfbee` · alwayss-snape

**Changed files**

- Tests: `M` tests/unit/test_validation.py

---

<!-- entry:2026-08-29T21:19:45+05:30 -->
## 2026-08-29 21:19 (+0530) · Cover conservative evidence matching

`c685f72` · alwayss-snape

**Changed files**

- Tests: `M` tests/unit/test_matcher.py

---

<!-- entry:2026-08-29T21:19:29+05:30 -->
## 2026-08-29 21:19 (+0530) · Preserve table-based DOCX resume layouts

`5460d07` · alwayss-snape

**Changed files**

- Rendering: `M` app/rendering/docx_patcher.py

**Structure delta**

- `app/rendering/docx_patcher.py`: added `DocxPatcher._replace_paragraph_text()`

---

<!-- entry:2026-08-29T21:19:08+05:30 -->
## 2026-08-29 21:19 (+0530) · Preview the rendered resume instead of plain Markdown

`729e2b4` · alwayss-snape

**Changed files**

- Entry points: `M` app/ui.py

---

<!-- entry:2026-08-29T21:18:54+05:30 -->
## 2026-08-29 21:18 (+0530) · Reject rewrites with unsupported claims

`c18b165` · alwayss-snape

**Changed files**

- Validation: `M` app/validation/factual.py

**Structure delta**

- `app/validation/factual.py`: added `FactualValidator._factual_terms()`

---

<!-- entry:2026-08-29T21:18:31+05:30 -->
## 2026-08-29 21:18 (+0530) · Require cited evidence for alignment score credit

`4c7e776` · alwayss-snape

**Changed files**

- Analysis: `M` app/analysis/scoring.py

---

<!-- entry:2026-08-29T21:18:20+05:30 -->
## 2026-08-29 21:18 (+0530) · Ground JD requirements in verbatim source text

`507d156` · alwayss-snape

**Changed files**

- Analysis: `M` app/analysis/jd_analyzer.py

**Structure delta**

- `app/analysis/jd_analyzer.py`: added `JDAnalyzer._category()`, `JDAnalyzer._is_requirement()`; removed `class LLMJDAnalysisOutput`

---

<!-- entry:2026-08-29T21:17:49+05:30 -->
## 2026-08-29 21:17 (+0530) · Harden evidence-only requirement matching

`209aa79` · alwayss-snape

**Changed files**

- Analysis: `M` app/analysis/matcher.py

**Structure delta**

- `app/analysis/matcher.py`: added `EvidenceMatcher._meaningful_tokens()`, `EvidenceMatcher._normalize_text()`; removed `EvidenceMatcher._normalize_term()`

---

<!-- entry:2026-08-29T21:09:09+05:30 -->
## 2026-08-29 21:09 (+0530) · fix: regex character class in skills normalizer

`dad4eff` · Kshitij Chaubey

**Changed files**

- Analysis: `M` app/analysis/resume_normalizer.py

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

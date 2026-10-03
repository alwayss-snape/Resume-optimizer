# Knowledge Graph — Resume-optimizer

> **Auto-generated** by `scripts/update_docs.py graph` (run by the pre-commit hook). Do not edit by hand —
> change the code, or the `STAGE_MAP` / `LAYERS` tables in the script. Machine-readable twin: `KNOWLEDGE_GRAPH.json`.

**57 app modules · 64 test files · 106 classes · 997 functions/methods · 20,176 lines of Python** · source hash `928e63aca1a3901c`

How to read this: every file sits at a point in a 3-D space — **where** it lives (path), **what** it is (layer), and **when** it runs (pipeline stage). Section 2 is that matrix; section 3 zooms into each module.

## Contents
1. [Directory map](#1-directory-map)
2. [Layer × Stage matrix](#2-layer--stage-matrix)
3. [Module cards](#3-module-cards)
4. [Dependency diagram](#4-dependency-diagram)
5. [Configuration keys](#5-configuration-keys)
6. [Prompts](#6-prompts)
7. [Gaps: untested and unmapped modules](#7-gaps-untested-and-unmapped-modules)

## 1. Directory map

```text
.env.example
ARCHITECTURE.md
BUILD.md
CLAUDE.md
README.md
pyproject.toml
.githooks/
  _python
  post-commit
  pre-commit
app/
  cli.py                                         check_llm(), write_proposals(), _without_mirrors(), read_proposals(), …
  analysis/
    change_proposal.py                           ChangeProposal
    checklist.py                                 Job conditions that aren't keywords (P8.20).
    experience.py                                Years of experience from role date ranges (P1.5), and the page target
    gap_questions.py                             Suggest-and-confirm gaps (P3.1): ask, never assume.
    jd_analyzer.py                               JDAnalyzer
    keyword_match.py                             Keyword-level match rate, the headline score (P1.2).
    matcher.py                                   EvidenceMatcher
    resume_normalizer.py                         ResumeNormalizer
    rewriter.py                                  LLMRewriter
    scoring.py                                   ScoreComponents, AlignmentScorer
    semantic_matcher.py                          Semantic (embedding-based) matching layer.
    skills_tailor.py                             Skills tailoring (P1.6), deterministic: no LLM, nothing added.
    structure_extractor.py                       LLM-assisted resume structure extraction with a verbatim guard (P1.13).
    summary_writer.py                            Tailored professional summary (P1.5).
    tailor_planner.py                            TailoringPlanner
    terminology.py                               flat_alias_to_canonical(), normalize_phrase()
  api/
    __init__.py
    forms.py                                     What the review form sends, turned into what TailorService takes (P5.1…
    main.py                                      The web app (P5.1): `uvicorn app.api.main:app`.
    routes.py                                    HTTP endpoints, one per step of the review flow (P5.1).
    sessions.py                                  Per-visitor state for the web API (P5.1).
  config/
    settings.py                                  Settings
  domain/
    evidence.py                                  Evidence
    job.py                                       Requirement, JobDescription
    report.py                                    Match, KeywordRow, KeywordMatchReport, TailoringReport
    resume.py                                    Candidate, ResumeBullet, Role, Experience, Project, Education, Section…
    resume_document.py                           ResumePresentation, ResumeSource, ResumeRevision, ResumeDocument
    tailoring.py                                 TailoringAction, TailoringPlan
  eval/
    __init__.py                                  Evaluation harness (P4.1): run resume + JD cases through the pipeline …
    __main__.py                                  python -m app.eval run [--live] [--tailor] [--case NAME] [--compare BA…
    golden.py                                    Canonical projection of a parsed resume, compared against hand-checked
    harness.py                                   Run evaluation cases through the pipeline and collect metrics (P4.1).
    judge.py                                     LLM-as-judge for the evaluation harness (P4.3).
  ingestion/
    docx.py                                      RawBlock, RawDocument, DocxParser
    ocr.py                                       OCREngine
    pdf.py                                       _Line, PdfParser
  llm/
    client.py                                    LLMClient
    schemas.py                                   LLMResponse, LLMError, LLMConnectionError, LLMTimeoutError, LLMInvalid…
    prompts/
      final_review.txt
      jd_analysis.txt
      judge_pairwise.txt
      rewrite_bullet.txt
      rewrite_role.txt
      summary.txt
  rendering/
    document_map.py                              DocumentLocation, DocumentMap
    docx_patcher.py                              DocxPatcher
    html_renderer.py                             HtmlResumeRenderer
    layout.py                                    Shared layout rules for the ATS template (P2.1).
    page_fit.py                                  Page-fit loop (P2.4): render, count pages, trim, render again.
    pdf_converter.py                             PdfConverter
    review_view.py                               What the proposal review screen shows (P3.4, served by the web API sin…
    template_renderer.py                         TemplateRenderer
  services/
    arrange.py                                   Arrange and edit before download (P8.13–P8.16).
    profile_store.py                             Local profile of facts the user has confirmed (P3.2).
    run_manager.py                               RunManager
    tailor.py                                    TailorService
  validation/
    content_lint.py                              Content checks on the finished resume (P2.6). Deterministic, no LLM.
    coverage.py                                  Content coverage (P8.2): does every line of the uploaded resume reach …
    factual.py                                   ClaimCheck, ValidationResult, FactualValidator
    output.py                                    OutputQAValidator
    safety.py                                    SafetyGuard
    structural.py                                StructuralValidator
scripts/
  autocommit.sh
  benchmark_model.py                             Benchmark local LLM latency and availability via Ollama.
  check_dependencies.py                          Simple dependency checker for LibreOffice and Ollama.
  create_sample_docx.py                          Generate sample fixture DOCX resume for testing.
  create_sample_pdf.py                           Generate sample PDF resume fixture using PyMuPDF.
  install_hooks.sh
  make_eval_cases.py                             Generate the anonymized evaluation cases (P4.2).
  make_persona_cases.py                          Turn the 2026-10-02 user-testing personas into eval cases (P8.1).
  update_docs.py                                 Regenerate the repo's living docs: the knowledge graph and the change …
tests/
  conftest.py                                    Test-wide isolation from the developer's .env.
  fixtures/
    jds/
      replica_layout_jd.txt
      sample.txt
    resumes/
      make_replica_layout_pdf.py                 Generate replica_layout.pdf: an anonymized resume with the same PDF la…
      replica_layout.golden.json
      replica_layout.pdf
      sample.docx
      sample.pdf
  integration/
    test_arrange.py                              P8.13–P8.16: arrange and edit after tailoring, with no LLM call.
    test_coverage_tailor.py                      P8.2: tailoring reports source lines that never reach the output, fails
    test_end_to_end.py                           test_integration_docx_pipeline(), test_integration_pdf_pipeline(), tes…
    test_eval_cases.py                           P4.2: every generated anonymized case must reproduce its expected.json
    test_parse_golden.py                         Parse a resume and compare it, field by field, with a hand-checked gol…
    test_persona_cases.py                        P8.1: the cross-domain user-testing personas as eval cases (offline, n…
    test_preserve_rewrite_end_to_end.py          test_approved_rewrite_appears_in_all_outputs()
  unit/
    test_api.py                                  Web API (P5.1): the full flow through HTTP, plus the shared form helpe…
    test_ats_round_trip.py                       P2.5: the rendered template must read back exactly as rendered, and the
    test_check_parsed_resume.py                  P3.5: "Check parsed resume" step: corrections applied by the service
    test_checklist_p820.py                       P8.20: job conditions that aren't keywords, apart from the score.
    test_cli.py                                  test_tailor_service_analyze_only(), test_tailor_service_end_to_end_doc…
    test_cli_parity.py                           P3.6: progress reporting, and the CLI doing what the UI does (review,
    test_contact_p84.py                          P8.4: phone numbers in any common grouping, and links with any common
    test_content_lint.py                         P2.6: deterministic content checks on the finished resume.
    test_coverage.py                             P8.2: content coverage of the output against the source lines.
    test_dates_p86.py                            P8.6: date formats from outside the US tech norm.
    test_docx_parser.py                          test_docx_parser_sample(), test_docx_parser_file_not_found()
    test_docx_renderer.py                        test_docx_patcher_preserve_mode(), test_template_renderer_ats_mode(), …
    test_education_p88.py                        P8.8: one-line education entries stay separate, details stay with their
    test_env.py                                  test_environment_baseline()
    test_eval_harness.py                         Evaluation harness (P4.1).
    test_experience.py                           P2.3: years of experience (overlaps merged) -> 1 or 2 target pages.
    test_fact_check_p89.py                       P8.9: the fact check catches wording borrowed from the job description,
    test_gap_questions.py                        Suggest-and-confirm gaps (P3.1).
    test_html_renderer.py                        test_html_renderer_outputs_ats_sections_and_escapes_content()
    test_jd_analyzer.py                          test_jd_analyzer_heuristic(), test_heading_variants_are_not_extracted_…
    test_jd_analyzer_llm.py                      _FakeLLMClient
    test_jd_analyzer_v2.py                       JD analysis v2 (P1.1): title/company without labels, whole-line
    test_jd_p818.py                              P8.18: JD cleanup, an honest offline fallback, and requirement statuses
    test_job_lines_p85.py                        P8.5: job-line formats outside tech: title / company / location / dates
    test_judge.py                                P4.3: LLM-as-judge (rubric + position-swapped pairwise), with a fake
    test_kept_sections_p83.py                    P8.3: sections the model has no fields for are kept verbatim under the…
    test_keyword_match.py                        Keyword-level match rate as the headline score (P1.2).
    test_layouts_p87.py                          P8.7: text boxes, a name in a separated page header, "·" bullets.
    test_llm_client.py                           SampleSchema
    test_matcher.py                              test_evidence_matcher_exact_and_alias(), test_one_generic_word_cannot_…
    test_matching_p817.py                        P8.17: a fairer match for non-tech resumes.
    test_new_role.py                             P3.3: add a job that isn't on the resume yet.
    test_page_fit.py                             P2.4: the page-fit loop trims in a fixed order, keeps minimums, reports
    test_parser_regressions_p42.py               Regression tests from the independent review of P4.2: inputs outside t…
    test_parsing_fixes_p19.py                    P1.9: links (DOCX hyperlinks, PDF link annotations, URLs in text),
    test_pdf_converter.py                        test_pdf_converter_find_binary_or_graceful_none(), test_output_qa_vali…
    test_pdf_parser.py                           test_pdf_parser_text_layer(), test_pdf_parser_file_not_found(), test_m…
    test_profile_store.py                        P3.2: confirmed gap answers are saved locally and offered on the next …
    test_project_rewrites.py                     Project bullets go through the same plan -> rewrite -> validate flow (…
    test_resume_document.py                      test_resume_document_has_versioned_json_snapshot(), test_resume_docume…
    test_resume_model_v2.py                      Resume model v2 (P1.12): several roles at one company, project
    test_resume_normalizer.py                    test_resume_normalizer(), _normalize_replica(), test_replica_header_su…
    test_review_view.py                          P3.4: the proposal review screen (diff, badges, breakdown, gap table,
    test_rewriter.py                             test_rewriter_deterministic_fallback(), test_rewrite_bullet_parses_str…
    test_scoring.py                              _req(), _match(), test_semantic_partial_excluded_from_headline_score()…
    test_semantic_matcher.py                     Tests for SemanticMatcher.
    test_skills_tailor.py                        Skills tailoring (P1.6): reorder by JD relevance, JD spelling, never a…
    test_stage_h_review.py                       Regressions from the independent review of Stage H (P8.1–P8.8): ordina…
    test_structure_extractor.py                  LLM-assisted structure extraction with a verbatim guard (P1.13).
    test_stuffing_p819.py                        P8.19: a Skills line pasted from the JD no longer beats real experienc…
    test_summary_writer.py                       Summary tailoring (P1.5) and years of experience from dates.
    test_tailor_planner.py                       test_tailor_planner(), test_semantic_only_match_produces_rewrite_with_…
    test_tailor_resume_flow.py                   tailor_resume orchestration: pre-approved proposals and Strict Factual…
    test_tailor_service_addition.py              _service(), test_incorporate_user_addition_appends_bullet_to_most_rece…
    test_template_layout.py                      P2.1: the ATS template (A4, Arial, standard headings, section order,
    test_template_renderer_standalone.py         _full_text(), test_template_renderer_ats_mode(), test_template_rendere…
    test_validation.py                           test_factual_validator_preserves_grounded_claims(), test_factual_valid…
```

## 2. Layer × Stage matrix

Rows = layer (what kind of code), columns = pipeline stage (when it runs during a tailoring run). Orchestrators (`tailor.py`, `ui.py`, `cli.py`) span every stage and are listed once below the table.

| Layer | 1 Ingest | 2 Normalize | 3 JD analysis | 4 Match | 5 Score | 6 Plan | 7 Rewrite | 8 Validate | 9 Render | 10 Report |
|---|---|---|---|---|---|---|---|---|---|---|
| **Ingestion** | `docx`<br>`ocr`<br>`pdf` | · | · | · | · | · | · | · | · | · |
| **Analysis** | · | `experience`<br>`resume_normalizer`<br>`structure_extractor` | `jd_analyzer` | `checklist`<br>`matcher`<br>`semantic_matcher`<br>`terminology` | `keyword_match`<br>`scoring` | `gap_questions`<br>`tailor_planner` | `change_proposal`<br>`experience`<br>`rewriter`<br>`skills_tailor`<br>`summary_writer` | · | · | · |
| **LLM** | · | · | `client`<br>`schemas` | · | · | · | `client`<br>`schemas` | · | · | · |
| **Validation** | · | · | `safety` | · | · | · | · | `content_lint`<br>`coverage`<br>`factual`<br>`output`<br>`structural` | · | · |
| **Rendering** | `document_map` | · | · | · | · | · | `review_view` | · | `document_map`<br>`docx_patcher`<br>`html_renderer`<br>`layout`<br>`page_fit`<br>`pdf_converter`<br>`template_renderer` | · |
| **Domain models** | · | `evidence`<br>`resume`<br>`resume_document` | `job` | `evidence`<br>`report` | `report` | `tailoring` | · | · | `resume_document` | · |
| **Services** | · | · | · | · | · | · | `profile_store` | · | `arrange` | `run_manager` |
| **Web API** | · | · | · | · | · | · | `forms` | · | · | `forms`<br>`sessions` |

Spanning all stages: `app/api/main.py`, `app/api/routes.py`, `app/cli.py`, `app/eval/harness.py`, `app/services/tailor.py`

## 3. Module cards

### `app/analysis/change_proposal.py`

**Layer:** Analysis · **Stage:** 7 Rewrite · **Lines:** 88

- class **`ChangeProposal`** ([app/analysis/change_proposal.py:6](../app/analysis/change_proposal.py#L6)) — Richer change proposal schema for review and audit.
  - `model_dump()` :48
  - `semantic_id()` :63
  - `source_id()` :73
  - `rewritten_text()` :82
- **Imported by:** `analysis/rewriter.py`, `analysis/skills_tailor.py`, `analysis/summary_writer.py`
- **Tested by:** `tests/unit/test_api.py`, `tests/unit/test_review_view.py`, `tests/unit/test_skills_tailor.py`, `tests/unit/test_summary_writer.py`, `tests/unit/test_validation.py`

### `app/analysis/checklist.py`

**Layer:** Analysis · **Stage:** 4 Match · **Lines:** 72

_Job conditions that aren't keywords (P8.20)._

- class **`Condition`** ([app/analysis/checklist.py:41](../app/analysis/checklist.py#L41))
- function **`build_checklist()`** ([app/analysis/checklist.py:52](../app/analysis/checklist.py#L52))
- **Imports:** `analysis/experience.py`, `domain/job.py`, `domain/resume.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_checklist_p820.py`

### `app/analysis/experience.py`

**Layer:** Analysis · **Stage:** 2 Normalize, 7 Rewrite · **Lines:** 150

_Years of experience from role date ranges (P1.5), and the page target_

- function **`is_ongoing()`** ([app/analysis/experience.py:27](../app/analysis/experience.py#L27)) — 'Present' / 'Current' / 'Till Date' / ... : the role hasn't ended.
- function **`day_first()`** ([app/analysis/experience.py:32](../app/analysis/experience.py#L32)) — For "dd/mm/yyyy" vs "mm/dd/yyyy": True when any value can only be
- function **`parse_month()`** ([app/analysis/experience.py:48](../app/analysis/experience.py#L48)) — 'August 2024' / 'Aug. 2024' / '08/2024' / '31/08/2024' / '2024-08' /
- function **`future_dates()`** ([app/analysis/experience.py:91](../app/analysis/experience.py#L91)) — Roles whose start date is after this month (P8.6): usually a typo or a
- function **`role_intervals()`** ([app/analysis/experience.py:106](../app/analysis/experience.py#L106)) — Each dated role as [start, end] in absolute months (year*12 + month).
- function **`years_of_experience()`** ([app/analysis/experience.py:124](../app/analysis/experience.py#L124)) — Total months covered by any role (overlaps merged), in years.
- function **`years_phrase()`** ([app/analysis/experience.py:136](../app/analysis/experience.py#L136)) — How a resume states it: '4+ years', '1 year', or None under 1 year.
- function **`target_pages()`** ([app/analysis/experience.py:148](../app/analysis/experience.py#L148)) — How many A4 pages the tailored resume should fill.
- **Imports:** `domain/resume.py`
- **Imported by:** `analysis/checklist.py`, `analysis/summary_writer.py`, `eval/harness.py`, `rendering/layout.py`, `rendering/page_fit.py`, `services/arrange.py`, `services/tailor.py`, `validation/content_lint.py`
- **Tested by:** `tests/unit/test_dates_p86.py`, `tests/unit/test_experience.py`, `tests/unit/test_summary_writer.py`

### `app/analysis/gap_questions.py`

**Layer:** Analysis · **Stage:** 6 Plan · **Lines:** 163

_Suggest-and-confirm gaps (P3.1): ask, never assume._

- class **`GapQuestion`** ([app/analysis/gap_questions.py:20](../app/analysis/gap_questions.py#L20))
- class **`GapAnswer`** ([app/analysis/gap_questions.py:38](../app/analysis/gap_questions.py#L38))
- function **`_degree_level()`** ([app/analysis/gap_questions.py:62](../app/analysis/gap_questions.py#L62))
- function **`infer_kind()`** ([app/analysis/gap_questions.py:77](../app/analysis/gap_questions.py#L77)) — The keyword's kind when the JD analysis couldn't tell (offline it
- function **`partly_shown()`** ([app/analysis/gap_questions.py:91](../app/analysis/gap_questions.py#L91)) — The resume already shows this, or one of its alternatives (P8.12):
- function **`_wording()`** ([app/analysis/gap_questions.py:116](../app/analysis/gap_questions.py#L116)) — (question, tick label) for what is being asked.
- function **`build_questions()`** ([app/analysis/gap_questions.py:130](../app/analysis/gap_questions.py#L130))
- **Imports:** `analysis/keyword_match.py`, `domain/job.py`, `domain/report.py`
- **Imported by:** `analysis/keyword_match.py`, `cli.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_api.py`, `tests/unit/test_gap_questions.py`, `tests/unit/test_profile_store.py`

### `app/analysis/jd_analyzer.py`

**Layer:** Analysis · **Stage:** 3 JD analysis · **Lines:** 502

- class **`JDAnalyzer`** ([app/analysis/jd_analyzer.py:11](../app/analysis/jd_analyzer.py#L11)) — Extract only text that is visibly present in the supplied job description.
  - `__init__()` :65
  - `clean_text()` :103 — A pasted JD as plain text (P8.18): HTML tags and entities removed
  - `too_short()` :122 — Too little to score against (P8.18: a two-word JD scored 100%).
  - `_not_benefit()` :126
  - `extract_keywords_from_text()` :130 — Stopgap keyword extraction: keep only technical-looking terms,
  - `_category()` :216
  - `_clean_line()` :229 — Strip a bullet marker, including private-use glyphs pasted from Word/PDF.
  - `_is_heading()` :234 — A section heading: the known patterns, an ALL-CAPS short line
  - `_is_requirement()` :251
  - `_reflow_lines()` :260 — Undo hard line-wrapping from pasted JDs (job boards/PDFs often wrap
  - `_verbatim()` :298 — The JD's own spelling of `value` if it occurs in the JD (case- and
  - `_verbatim_list()` :308
  - `_contains_term()` :319 — Whole-term containment: "A/B" is in "A/B testing", "ML" is not in "MLflow".
  - `count_occurrences()` :324 — Whole-term, case-insensitive count ("R" doesn't match "React").
  - `_heuristic_title_company()` :330
  - `_seniority()` :351
  - `_years()` :358
  - `_llm_analyze()` :366 — One structured call: metadata, requirement lines by index, skills.
  - `analyze()` :394
- **Imports:** `analysis/terminology.py`, `domain/job.py`, `llm/client.py`, `llm/schemas.py`
- **Imported by:** `api/routes.py`, `eval/harness.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_checklist_p820.py`, `tests/unit/test_jd_analyzer.py`, `tests/unit/test_jd_analyzer_llm.py`, `tests/unit/test_jd_analyzer_v2.py`, `tests/unit/test_jd_p818.py`, `tests/unit/test_parser_regressions_p42.py`
- **Prompts:** `llm/prompts/jd_analysis.txt`

### `app/analysis/keyword_match.py`

**Layer:** Analysis · **Stage:** 5 Score · **Lines:** 340

_Keyword-level match rate, the headline score (P1.2)._

- class **`KeywordMatcher`** ([app/analysis/keyword_match.py:195](../app/analysis/keyword_match.py#L195))
  - `__init__()` :196
  - `_slash_parts()` :200 — "Compact/NLC", "English/Spanish": words joined by a slash, each
  - `_found_with_credit()` :210
  - `_find()` :232
  - `_title_credit()` :259
  - `match()` :269
- function **`_stem()`** ([app/analysis/keyword_match.py:54](../app/analysis/keyword_match.py#L54)) — Plural- and verb-form-insensitive: "communicate", "communicated" and
- function **`_alias()`** ([app/analysis/keyword_match.py:72](../app/analysis/keyword_match.py#L72))
- function **`tokens()`** ([app/analysis/keyword_match.py:82](../app/analysis/keyword_match.py#L82)) — Lowercased, alias-canonical, plural- and verb-form-insensitive tokens.
- function **`_contains_seq()`** ([app/analysis/keyword_match.py:88](../app/analysis/keyword_match.py#L88))
- function **`resume_sections()`** ([app/analysis/keyword_match.py:93](../app/analysis/keyword_match.py#L93)) — (label, text) for every part of the resume a recruiter or ATS reads.
- function **`is_place()`** ([app/analysis/keyword_match.py:141](../app/analysis/keyword_match.py#L141)) — A location the JD names, not a skill (P8.17: "Arizona" and "DC" were
- function **`definitions()`** ([app/analysis/keyword_match.py:160](../app/analysis/keyword_match.py#L160)) — acronym -> expansion (both lowercase), from "Full Name (ACR)" in texts.
- function **`alternatives_of()`** ([app/analysis/keyword_match.py:178](../app/analysis/keyword_match.py#L178)) — Token sequences that count as the keyword: "OSHA 10 or 30" -> OSHA 10,
- function **`reconcile()`** ([app/analysis/keyword_match.py:318](../app/analysis/keyword_match.py#L318)) — A requirement can't read "not shown" while every job keyword in it is
- **Imports:** `analysis/gap_questions.py`, `analysis/resume_normalizer.py`, `analysis/terminology.py`, `domain/job.py`, `domain/report.py`, `domain/resume.py`
- **Imported by:** `analysis/gap_questions.py`, `analysis/skills_tailor.py`, `analysis/tailor_planner.py`, `eval/harness.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_gap_questions.py`, `tests/unit/test_jd_p818.py`, `tests/unit/test_keyword_match.py`, `tests/unit/test_matching_p817.py`, `tests/unit/test_parser_regressions_p42.py`, `tests/unit/test_skills_tailor.py`, `tests/unit/test_stuffing_p819.py`, `tests/unit/test_summary_writer.py`

### `app/analysis/matcher.py`

**Layer:** Analysis · **Stage:** 4 Match · **Lines:** 146

- class **`EvidenceMatcher`** ([app/analysis/matcher.py:20](../app/analysis/matcher.py#L20)) — Deterministic, evidence-only matcher.
  - `__init__()` :27
  - `_normalize_text()` :30
  - `_extract_key_tokens()` :38
  - `_meaningful_tokens()` :42
  - `_extract_requirement_units()` :45 — Break a requirement into comparable 'units' for coverage scoring.
  - `match()` :89
- **Imports:** `analysis/terminology.py`, `domain/evidence.py`, `domain/job.py`, `domain/report.py`, `llm/client.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_matcher.py`

### `app/analysis/resume_normalizer.py`

**Layer:** Analysis · **Stage:** 2 Normalize · **Lines:** 1246

- class **`ResumeNormalizer`** ([app/analysis/resume_normalizer.py:9](../app/analysis/resume_normalizer.py#L9))
  - `find_phone()` :62 — The first phone number in a line, as written, or None.
  - `_header_urls()` :85
  - `_is_headline()` :98 — A short title line under the name, e.g. 'Senior Data Scientist |
  - `section_kind()` :148 — 'Clinical Rotations' -> 'other', 'Work History' -> 'experience',
  - `_heading_sig()` :157 — How a heading line is set: capitals, bold, size, Word style.
  - `_section_heading_sigs()` :163 — The look of the lines this document uses as section headings.
  - `_styled_as_heading()` :168 — Set like the document's section headings, or (when none was
  - `_heading_kind()` :179 — The section a heading line starts, or None when the line is content.
  - `_display_heading()` :222 — 'CLINICAL ROTATIONS' -> 'Clinical Rotations'; mixed case kept.
  - `_header_segments()` :230 — 'Austin, TX · a@b.com · 512-555-0199' -> its parts.
  - `_looks_like_name()` :234
  - `_looks_like_location()` :246 — A place, never a job title ("Backend Engineer, Payments" or
  - `_is_detail()` :254 — A header part worth keeping as is: not contact data (email,
  - `_is_section_title()` :304
  - `_looks_like_title()` :334
  - `_split_title_company()` :337 — 'Title | Company | Place', 'Company — Title', 'Title — Team — Company'
  - `_title_score()` :354 — 2 when a role word ends the phrase ("Data Analyst"), 1 when it's
  - `_split_company_location()` :373 — 'Banner Medical Center, Phoenix, AZ' -> ('Banner Medical Center',
  - `_split_comma_job()` :391 — 'Shift Supervisor, Starbucks, Atlanta GA' -> (title, company,
  - `_ends_with_suffix()` :407 — "CloudMetrics Inc." ends with a full stop but is a company, not a sentence.
  - `_next_is_meta_line()` :412 — The ATS template prints 'Company · Location' under the title line.
  - `_trim()` :425 — Strip separators left around removed dates, keeping a closing
  - `_split_skill_line()` :441 — 'Languages: Python, SQL<tab>Frameworks: Pandas, and XGBoost' ->
  - `_skill_items()` :462
  - `_split_education_line()` :480 — 'B.S. Biology, University of Texas at Austin, 2016' -> (degree,
  - `_looks_like_degree()` :526 — 'B.Tech in Computer Science' yes; 'State University' no.
  - `_split_middle_dot()` :532 — 'Acme Corp · Pune, India' -> ('Acme Corp', 'Pune, India'), the
  - `_is_dated_line()` :541 — A job title/company line carrying a date range or year. A date
  - `_header_range()` :556 — A date range inside a job header line, or None. Trailing ranges
  - `_experience_line_kind()` :573 — 'dated' (title and/or company with dates), 'header_line' (a short
  - `_add_role()` :592 — Record a role; the first one also fills the entry's title/dates.
  - `_merge_links()` :602 — Profile links from the file's hyperlinks and from URLs written in
  - `_trailing_dates()` :616 — (match, start, end) for a trailing date range or single date.
  - `_extract_date_range()` :626
  - `_strip_date_range()` :632
  - `_parse_title_and_dates()` :636 — 'Data Scientist II | August 2024 - Present' ->
  - `_split_list_items()` :651 — Items of a certification / award line. ';' always separates
  - `_split_respecting_parens()` :670 — Split on sep_chars, but never inside ( ) or [ ] groups — so
  - `normalize()` :693
- **Imports:** `domain/evidence.py`, `domain/resume.py`, `domain/resume_document.py`, `ingestion/docx.py`
- **Imported by:** `analysis/keyword_match.py`, `analysis/structure_extractor.py`, `eval/golden.py`, `services/tailor.py`, `validation/output.py`
- **Tested by:** `tests/integration/test_preserve_rewrite_end_to_end.py`, `tests/unit/test_ats_round_trip.py`, `tests/unit/test_contact_p84.py`, `tests/unit/test_dates_p86.py`, `tests/unit/test_education_p88.py`, `tests/unit/test_job_lines_p85.py`, `tests/unit/test_kept_sections_p83.py`, `tests/unit/test_layouts_p87.py`, `tests/unit/test_parser_regressions_p42.py`, `tests/unit/test_parsing_fixes_p19.py`, `tests/unit/test_resume_model_v2.py`, `tests/unit/test_resume_normalizer.py`, `tests/unit/test_stage_h_review.py`, `tests/unit/test_structure_extractor.py`, `tests/unit/test_tailor_resume_flow.py`

### `app/analysis/rewriter.py`

**Layer:** Analysis · **Stage:** 7 Rewrite · **Lines:** 293

- class **`LLMRewriter`** ([app/analysis/rewriter.py:69](../app/analysis/rewriter.py#L69))
  - `__init__()` :70
  - `rewrite_bullet()` :73 — Rewrite (or, given a single free-text `original_text` with no
  - `rewrite_bullet_with_status()` :93 — Like rewrite_bullet, plus what happened, so failures are visible
  - `rewrite_role()` :151 — Rewrite several bullets of one role in ONE call (P1.4).
  - `execute_plan()` :210 — One LLM call per role (P1.4): all of a job's bullets that the
- function **`normalize_llm_text()`** ([app/analysis/rewriter.py:27](../app/analysis/rewriter.py#L27))
- function **`_same_wording()`** ([app/analysis/rewriter.py:34](../app/analysis/rewriter.py#L34)) — Equal apart from case, whitespace and closing punctuation, so adding a
- function **`breaks_bullet_rules()`** ([app/analysis/rewriter.py:50](../app/analysis/rewriter.py#L50)) — True when a bullet is over the word limit or uses a filler word.
- **Imports:** `analysis/change_proposal.py`, `domain/evidence.py`, `domain/job.py`, `domain/resume.py`, `domain/tailoring.py`, `llm/client.py`, `llm/schemas.py`
- **Imported by:** `analysis/summary_writer.py`, `rendering/docx_patcher.py`, `services/tailor.py`, `validation/content_lint.py`, `validation/factual.py`
- **Tested by:** `tests/integration/test_preserve_rewrite_end_to_end.py`, `tests/unit/test_docx_renderer.py`, `tests/unit/test_fact_check_p89.py`, `tests/unit/test_project_rewrites.py`, `tests/unit/test_rewriter.py`, `tests/unit/test_tailor_planner.py`, `tests/unit/test_tailor_resume_flow.py`, `tests/unit/test_validation.py`
- **Prompts:** `llm/prompts/rewrite_bullet.txt`, `llm/prompts/rewrite_role.txt`

### `app/analysis/scoring.py`

**Layer:** Analysis · **Stage:** 5 Score · **Lines:** 134

- class **`ScoreComponents`** ([app/analysis/scoring.py:7](../app/analysis/scoring.py#L7))
- class **`AlignmentScorer`** ([app/analysis/scoring.py:31](../app/analysis/scoring.py#L31)) — A transparent weighted average of evidence-backed requirement coverage.
  - `calculate_components()` :43
  - `_compute()` :46
  - `calculate_score()` :123
- **Imports:** `domain/job.py`, `domain/report.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_matcher.py`, `tests/unit/test_scoring.py`

### `app/analysis/semantic_matcher.py`

**Layer:** Analysis · **Stage:** 4 Match · **Lines:** 172

_Semantic (embedding-based) matching layer._

- class **`SemanticMatcher`** ([app/analysis/semantic_matcher.py:42](../app/analysis/semantic_matcher.py#L42)) — Adds SEMANTIC_PARTIAL matches for requirements the deterministic
  - `__init__()` :54
  - `_get_embedder()` :77
  - `match()` :103 — Returns a new match list: every non-MISSING match from
- function **`_cosine_similarity()`** ([app/analysis/semantic_matcher.py:33](../app/analysis/semantic_matcher.py#L33))
- **Imports:** `config/settings.py`, `domain/evidence.py`, `domain/job.py`, `domain/report.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_semantic_matcher.py`

### `app/analysis/skills_tailor.py`

**Layer:** Analysis · **Stage:** 7 Rewrite · **Lines:** 91

_Skills tailoring (P1.6), deterministic: no LLM, nothing added._

- class **`SkillsTailor`** ([app/analysis/skills_tailor.py:43](../app/analysis/skills_tailor.py#L43))
  - `tailor()` :44
  - `propose()` :71 — A skills proposal, or None when nothing would change.
- function **`format_skills()`** ([app/analysis/skills_tailor.py:21](../app/analysis/skills_tailor.py#L21)) — One "Category: a, b, c" line per category (the editable form).
- function **`parse_skills()`** ([app/analysis/skills_tailor.py:26](../app/analysis/skills_tailor.py#L26)) — Inverse of format_skills; a line without a label goes under "Skills".
- function **`_key()`** ([app/analysis/skills_tailor.py:39](../app/analysis/skills_tailor.py#L39))
- function **`unknown_skills()`** ([app/analysis/skills_tailor.py:88](../app/analysis/skills_tailor.py#L88)) — Skills in `proposed` that aren't in `original` under any spelling.
- **Imports:** `analysis/change_proposal.py`, `analysis/keyword_match.py`, `domain/report.py`, `domain/resume.py`
- **Imported by:** `services/tailor.py`, `validation/factual.py`
- **Tested by:** `tests/unit/test_skills_tailor.py`

### `app/analysis/structure_extractor.py`

**Layer:** Analysis · **Stage:** 2 Normalize · **Lines:** 173

_LLM-assisted resume structure extraction with a verbatim guard (P1.13)._

- class **`LineLabel`** ([app/analysis/structure_extractor.py:43](../app/analysis/structure_extractor.py#L43))
- class **`ResumeLineLabels`** ([app/analysis/structure_extractor.py:48](../app/analysis/structure_extractor.py#L48)) — Structural role of each numbered resume line, selected by INDEX. The
- class **`StructureExtractor`** ([app/analysis/structure_extractor.py:71](../app/analysis/structure_extractor.py#L71))
  - `__init__()` :76
  - `problems()` :82 — Signs that the deterministic parse misread the layout.
  - `label_lines()` :108 — Ask the LLM for a label per block index. None if unavailable or
  - `apply_labels()` :138 — A copy of raw_doc with each labelled block carrying a hint. Text
  - `improve()` :152 — Return the better of the deterministic parse and an LLM-guided
- **Imports:** `analysis/resume_normalizer.py`, `domain/evidence.py`, `domain/resume.py`, `domain/resume_document.py`, `ingestion/docx.py`, `llm/client.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_parsing_fixes_p19.py`, `tests/unit/test_structure_extractor.py`

### `app/analysis/summary_writer.py`

**Layer:** Analysis · **Stage:** 7 Rewrite · **Lines:** 153

_Tailored professional summary (P1.5)._

- class **`SummaryWriter`** ([app/analysis/summary_writer.py:33](../app/analysis/summary_writer.py#L33))
  - `__init__()` :34
  - `sane_title()` :41 — A title fit to print (P8.10: a misread "03/" became the summary's
  - `years_claim()` :50 — The years of experience the resume itself states, if it states
  - `facts()` :71 — The inputs code decides; the LLM only phrases them.
  - `propose()` :92 — A summary proposal, or None when there's nothing to write from
- **Imports:** `analysis/change_proposal.py`, `analysis/experience.py`, `analysis/rewriter.py`, `domain/evidence.py`, `domain/job.py`, `domain/report.py`, `domain/resume.py`, `llm/client.py`, `llm/schemas.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_summary_writer.py`
- **Prompts:** `llm/prompts/summary.txt`

### `app/analysis/tailor_planner.py`

**Layer:** Analysis · **Stage:** 6 Plan · **Lines:** 183

- class **`TailoringPlanner`** ([app/analysis/tailor_planner.py:35](../app/analysis/tailor_planner.py#L35)) — Planner v2 (P1.3): scores every experience bullet for relevance to the
  - `__init__()` :42
  - `_similarities()` :47 — bullets x requirements similarity in 0..1.
  - `create_plan()` :65
  - `rank_missing_requirements()` :166 — Order MISSING matches so the most important, still-unaddressed
- function **`_content()`** ([app/analysis/tailor_planner.py:25](../app/analysis/tailor_planner.py#L25))
- function **`_cosine()`** ([app/analysis/tailor_planner.py:29](../app/analysis/tailor_planner.py#L29))
- **Imports:** `analysis/keyword_match.py`, `domain/evidence.py`, `domain/job.py`, `domain/report.py`, `domain/resume.py`, `domain/tailoring.py`, `llm/client.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_project_rewrites.py`, `tests/unit/test_rewriter.py`, `tests/unit/test_tailor_planner.py`

### `app/analysis/terminology.py`

**Layer:** Analysis · **Stage:** 4 Match · **Lines:** 145

- function **`flat_alias_to_canonical()`** ([app/analysis/terminology.py:51](../app/analysis/terminology.py#L51)) — Build a flat alias->canonical map (e.g. 'k8s' -> 'kubernetes') for
- function **`normalize_phrase()`** ([app/analysis/terminology.py:61](../app/analysis/terminology.py#L61)) — Normalize a phrase to its canonical lowercased form and expand common acronyms.
- **Imported by:** `analysis/jd_analyzer.py`, `analysis/keyword_match.py`, `analysis/matcher.py`, `validation/factual.py`

### `app/api/__init__.py`

**Layer:** Web API · **Stage:** — · **Lines:** 0

- **Imported by:** `api/routes.py`
- **Tested by:** `tests/unit/test_api.py`

### `app/api/forms.py`

**Layer:** Web API · **Stage:** 7 Rewrite, 10 Report · **Lines:** 108

_What the review form sends, turned into what TailorService takes (P5.1)._

- function **`current_provider()`** ([app/api/forms.py:21](../app/api/forms.py#L21))
- function **`model_options()`** ([app/api/forms.py:25](../app/api/forms.py#L25)) — Models offered for the configured provider. The configured default
- function **`proposal_text()`** ([app/api/forms.py:38](../app/api/forms.py#L38))
- function **`preapproved()`** ([app/api/forms.py:42](../app/api/forms.py#L42)) — The ticked proposals as dicts, carrying the user's edits. `edits`
- function **`resolve_target()`** ([app/api/forms.py:59](../app/api/forms.py#L59)) — "auto", "new_project" or a known experience id; anything else is
- function **`answer_counts()`** ([app/api/forms.py:67](../app/api/forms.py#L67)) — Unticking every keyword also withdraws a pre-filled answer the user
- function **`gap_answers()`** ([app/api/forms.py:74](../app/api/forms.py#L74)) — The answers that count. `inputs` maps a question id to {"ticked":
- function **`new_role()`** ([app/api/forms.py:90](../app/api/forms.py#L90)) — The "add a job" form (P3.3) -> (role dict for tailor_resume, error).
- **Imports:** `config/settings.py`

### `app/api/main.py`

**Layer:** Web API · **Stage:** all · **Lines:** 51

_The web app (P5.1): `uvicorn app.api.main:app`._

- function **`default_service()`** ([app/api/main.py:20](../app/api/main.py#L20))
- function **`create_app()`** ([app/api/main.py:27](../app/api/main.py#L27))
- **Imports:** `api/routes.py`, `api/sessions.py`, `config/settings.py`, `llm/client.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_api.py`

### `app/api/routes.py`

**Layer:** Web API · **Stage:** all · **Lines:** 550

_HTTP endpoints, one per step of the review flow (P5.1)._

- class **`ProposalsIn`** ([app/api/routes.py:43](../app/api/routes.py#L43))
- class **`SelectionItem`** ([app/api/routes.py:50](../app/api/routes.py#L50))
- class **`MatchPreviewIn`** ([app/api/routes.py:55](../app/api/routes.py#L55))
- class **`GapInput`** ([app/api/routes.py:59](../app/api/routes.py#L59))
- class **`AdditionIn`** ([app/api/routes.py:65](../app/api/routes.py#L65))
- class **`NewRoleIn`** ([app/api/routes.py:70](../app/api/routes.py#L70))
- class **`TailorIn`** ([app/api/routes.py:80](../app/api/routes.py#L80))
- class **`RateLimiter`** ([app/api/routes.py:94](../app/api/routes.py#L94)) — At most `limit` calls per `window` seconds per key (visitor IP).
  - `__init__()` :97
  - `check()` :102
- class **`ArrangeIn`** ([app/api/routes.py:466](../app/api/routes.py#L466))
- function **`rate_limited()`** ([app/api/routes.py:113](../app/api/routes.py#L113))
- function **`current_session()`** ([app/api/routes.py:117](../app/api/routes.py#L117))
- function **`_require()`** ([app/api/routes.py:124](../app/api/routes.py#L124))
- function **`_claim()`** ([app/api/routes.py:129](../app/api/routes.py#L129))
- function **`_save_upload()`** ([app/api/routes.py:134](../app/api/routes.py#L134)) — The upload as a temp file, after checking its type and size.
- function **`_check_jd()`** ([app/api/routes.py:150](../app/api/routes.py#L150))
- function **`_event()`** ([app/api/routes.py:159](../app/api/routes.py#L159))
- function **`_stream()`** ([app/api/routes.py:163](../app/api/routes.py#L163)) — Run `work(progress)` in a thread (the session must already be
- function **`_service()`** ([app/api/routes.py:198](../app/api/routes.py#L198)) — A TailorService for one step. With a session, saved gap answers come
- function **`_details()`** ([app/api/routes.py:210](../app/api/routes.py#L210)) — What the "check details" step shows and edits (P3.5).
- function **`_sections()`** ([app/api/routes.py:226](../app/api/routes.py#L226)) — Bullet id -> the job or project it belongs to, for grouping cards.
- function **`_proposal_out()`** ([app/api/routes.py:238](../app/api/routes.py#L238))
- function **`_match_out()`** ([app/api/routes.py:251](../app/api/routes.py#L251))
- function **`_selected()`** ([app/api/routes.py:257](../app/api/routes.py#L257))
- function **`health()`** ([app/api/routes.py:267](../app/api/routes.py#L267))
- function **`config()`** ([app/api/routes.py:272](../app/api/routes.py#L272))
- function **`_model()`** ([app/api/routes.py:279](../app/api/routes.py#L279))
- function **`analyze()`** ([app/api/routes.py:286](../app/api/routes.py#L286)) — "Just check my match": score only, nothing kept.
- function **`parse()`** ([app/api/routes.py:300](../app/api/routes.py#L300)) — Step 1: read the resume and start a fresh session for this run.
- function **`proposals()`** ([app/api/routes.py:333](../app/api/routes.py#L333)) — Step 2: apply the user's fixes, then draft rewrites and gap
- function **`match_preview()`** ([app/api/routes.py:384](../app/api/routes.py#L384)) — The match rate if the selected (and edited) proposals were applied.
- function **`tailor()`** ([app/api/routes.py:394](../app/api/routes.py#L394)) — Step 3: apply the review and generate the files. Streams progress.
- function **`_results_out()`** ([app/api/routes.py:434](../app/api/routes.py#L434)) — What the Results (and Arrange) screen gets after a run.
- function **`arrange()`** ([app/api/routes.py:474](../app/api/routes.py#L474)) — Re-render the tailored resume as the user arranged it (P8.13). No LLM
- function **`_result_path()`** ([app/api/routes.py:513](../app/api/routes.py#L513))
- function **`download()`** ([app/api/routes.py:521](../app/api/routes.py#L521))
- function **`preview()`** ([app/api/routes.py:529](../app/api/routes.py#L529)) — One page of the tailored PDF as a PNG (Chrome blocks embedded PDFs).
- function **`reset()`** ([app/api/routes.py:538](../app/api/routes.py#L538)) — Start over: delete this visitor's files and state. If a step is still
- **Imports:** `analysis/jd_analyzer.py`, `api/__init__.py`, `api/sessions.py`, `rendering/pdf_converter.py`, `rendering/review_view.py`, `services/arrange.py`
- **Imported by:** `api/main.py`
- **Tested by:** `tests/unit/test_api.py`

### `app/api/sessions.py`

**Layer:** Web API · **Stage:** 10 Report · **Lines:** 96

_Per-visitor state for the web API (P5.1)._

- class **`Session`** ([app/api/sessions.py:24](../app/api/sessions.py#L24))
  - `reset()` :37 — Delete the session's temp files and forget everything.
- class **`SessionStore`** ([app/api/sessions.py:56](../app/api/sessions.py#L56))
  - `__init__()` :57
  - `get()` :62
  - `create()` :70
  - `drop()` :76 — Forget a session now, deleting its temp files.
  - `sweep()` :82 — Drop sessions idle longer than the TTL; returns how many. A
- function **`remove_path()`** ([app/api/sessions.py:44](../app/api/sessions.py#L44))
- **Imports:** `services/profile_store.py`
- **Imported by:** `api/main.py`, `api/routes.py`
- **Tested by:** `tests/unit/test_api.py`

### `app/cli.py`

**Layer:** Entry points · **Stage:** all · **Lines:** 277

- function **`check_llm()`** ([app/cli.py:11](../app/cli.py#L11)) — One live, structured call to the configured provider. Returns an exit
- function **`write_proposals()`** ([app/cli.py:60](../app/cli.py#L60)) — Draft proposals and gap questions into an editable JSON file (P3.6),
- function **`_without_mirrors()`** ([app/cli.py:97](../app/cli.py#L97))
- function **`read_proposals()`** ([app/cli.py:101](../app/cli.py#L101)) — The edited proposals file -> tailor_resume keyword arguments, with
- function **`_print_progress()`** ([app/cli.py:171](../app/cli.py#L171))
- function **`main()`** ([app/cli.py:175](../app/cli.py#L175))
- **Imports:** `analysis/gap_questions.py`, `domain/job.py`, `llm/client.py`, `llm/schemas.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_cli.py`, `tests/unit/test_cli_parity.py`

### `app/config/settings.py`

**Layer:** Config · **Stage:** — · **Lines:** 66

- class **`Settings`** ([app/config/settings.py:4](../app/config/settings.py#L4))
- **Imported by:** `analysis/semantic_matcher.py`, `api/forms.py`, `api/main.py`, `eval/judge.py`, `llm/client.py`, `services/profile_store.py`
- **Tested by:** `tests/unit/test_profile_store.py`

### `app/domain/evidence.py`

**Layer:** Domain models · **Stage:** 2 Normalize, 4 Match · **Lines:** 22

- class **`Evidence`** ([app/domain/evidence.py:4](../app/domain/evidence.py#L4))
- **Imported by:** `analysis/matcher.py`, `analysis/resume_normalizer.py`, `analysis/rewriter.py`, `analysis/semantic_matcher.py`, `analysis/structure_extractor.py`, `analysis/summary_writer.py`, `analysis/tailor_planner.py`, `services/tailor.py`, `validation/factual.py`
- **Tested by:** `tests/unit/test_fact_check_p89.py`, `tests/unit/test_matcher.py`, `tests/unit/test_project_rewrites.py`, `tests/unit/test_resume_normalizer.py`, `tests/unit/test_rewriter.py`, `tests/unit/test_semantic_matcher.py`, `tests/unit/test_summary_writer.py`, `tests/unit/test_tailor_planner.py`, `tests/unit/test_tailor_service_addition.py`, `tests/unit/test_validation.py`

### `app/domain/job.py`

**Layer:** Domain models · **Stage:** 3 JD analysis · **Lines:** 45

- class **`Requirement`** ([app/domain/job.py:4](../app/domain/job.py#L4))
- class **`JobDescription`** ([app/domain/job.py:28](../app/domain/job.py#L28))
- **Imported by:** `analysis/checklist.py`, `analysis/gap_questions.py`, `analysis/jd_analyzer.py`, `analysis/keyword_match.py`, `analysis/matcher.py`, `analysis/rewriter.py`, `analysis/scoring.py`, `analysis/semantic_matcher.py`, `analysis/summary_writer.py`, `analysis/tailor_planner.py`, `cli.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_gap_questions.py`, `tests/unit/test_jd_analyzer.py`, `tests/unit/test_keyword_match.py`, `tests/unit/test_matcher.py`, `tests/unit/test_matching_p817.py`, `tests/unit/test_new_role.py`, `tests/unit/test_parser_regressions_p42.py`, `tests/unit/test_project_rewrites.py`, `tests/unit/test_review_view.py`, `tests/unit/test_rewriter.py`, `tests/unit/test_scoring.py`, `tests/unit/test_semantic_matcher.py`, `tests/unit/test_skills_tailor.py`, `tests/unit/test_stuffing_p819.py`, `tests/unit/test_summary_writer.py`, `tests/unit/test_tailor_planner.py`, `tests/unit/test_tailor_service_addition.py`

### `app/domain/report.py`

**Layer:** Domain models · **Stage:** 4 Match, 5 Score · **Lines:** 67

- class **`Match`** ([app/domain/report.py:8](../app/domain/report.py#L8))
- class **`KeywordRow`** ([app/domain/report.py:23](../app/domain/report.py#L23))
- class **`KeywordMatchReport`** ([app/domain/report.py:36](../app/domain/report.py#L36))
  - `matched()` :44
  - `missing()` :48
- class **`TailoringReport`** ([app/domain/report.py:53](../app/domain/report.py#L53))
- **Imported by:** `analysis/gap_questions.py`, `analysis/keyword_match.py`, `analysis/matcher.py`, `analysis/scoring.py`, `analysis/semantic_matcher.py`, `analysis/skills_tailor.py`, `analysis/summary_writer.py`, `analysis/tailor_planner.py`, `eval/harness.py`, `rendering/review_view.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_jd_p818.py`, `tests/unit/test_matcher.py`, `tests/unit/test_review_view.py`, `tests/unit/test_scoring.py`, `tests/unit/test_semantic_matcher.py`, `tests/unit/test_tailor_planner.py`, `tests/unit/test_tailor_service_addition.py`

### `app/domain/resume.py`

**Layer:** Domain models · **Stage:** 2 Normalize · **Lines:** 120

- class **`Candidate`** ([app/domain/resume.py:5](../app/domain/resume.py#L5))
  - `display_links()` :17 — Links as shown on a resume: 'linkedin.com/in/x', no scheme/www.
- class **`ResumeBullet`** ([app/domain/resume.py:21](../app/domain/resume.py#L21))
- class **`Role`** ([app/domain/resume.py:29](../app/domain/resume.py#L29)) — One title held at a company, e.g. 'Data Scientist II, Aug 2024 - Present'.
- class **`Experience`** ([app/domain/resume.py:35](../app/domain/resume.py#L35)) — One company entry. `title` / `start_date` / `end_date` describe the
  - `all_roles()` :57
  - `bullet_groups()` :64 — Consecutive bullets grouped by sub-heading, in document order.
- class **`Project`** ([app/domain/resume.py:74](../app/domain/resume.py#L74))
- class **`Education`** ([app/domain/resume.py:81](../app/domain/resume.py#L81))
- class **`SectionLine`** ([app/domain/resume.py:92](../app/domain/resume.py#L92))
- class **`OtherSection`** ([app/domain/resume.py:98](../app/domain/resume.py#L98)) — A section the resume model has no fields for (Publications, Bar
- class **`Resume`** ([app/domain/resume.py:110](../app/domain/resume.py#L110))
- **Imported by:** `analysis/checklist.py`, `analysis/experience.py`, `analysis/keyword_match.py`, `analysis/resume_normalizer.py`, `analysis/rewriter.py`, `analysis/skills_tailor.py`, `analysis/structure_extractor.py`, `analysis/summary_writer.py`, `analysis/tailor_planner.py`, `domain/resume_document.py`, `eval/golden.py`, `rendering/html_renderer.py`, `rendering/layout.py`, `rendering/page_fit.py`, `services/arrange.py`, `services/tailor.py`, `validation/content_lint.py`, `validation/structural.py`
- **Tested by:** `tests/unit/test_ats_round_trip.py`, `tests/unit/test_check_parsed_resume.py`, `tests/unit/test_checklist_p820.py`, `tests/unit/test_content_lint.py`, `tests/unit/test_dates_p86.py`, `tests/unit/test_docx_renderer.py`, `tests/unit/test_experience.py`, `tests/unit/test_gap_questions.py`, `tests/unit/test_html_renderer.py`, `tests/unit/test_jd_p818.py`, `tests/unit/test_keyword_match.py`, `tests/unit/test_matching_p817.py`, `tests/unit/test_new_role.py`, `tests/unit/test_page_fit.py`, `tests/unit/test_parser_regressions_p42.py`, `tests/unit/test_parsing_fixes_p19.py`, `tests/unit/test_project_rewrites.py`, `tests/unit/test_resume_document.py`, `tests/unit/test_resume_model_v2.py`, `tests/unit/test_resume_normalizer.py`, `tests/unit/test_review_view.py`, `tests/unit/test_rewriter.py`, `tests/unit/test_skills_tailor.py`, `tests/unit/test_stuffing_p819.py`, `tests/unit/test_summary_writer.py`, `tests/unit/test_tailor_planner.py`, `tests/unit/test_tailor_service_addition.py`, `tests/unit/test_template_layout.py`, `tests/unit/test_template_renderer_standalone.py`

### `app/domain/resume_document.py`

**Layer:** Domain models · **Stage:** 2 Normalize, 9 Render · **Lines:** 86

- class **`ResumePresentation`** ([app/domain/resume_document.py:10](../app/domain/resume_document.py#L10)) — Display choices; content remains in the canonical Resume model.
- class **`ResumeSource`** ([app/domain/resume_document.py:25](../app/domain/resume_document.py#L25))
- class **`ResumeRevision`** ([app/domain/resume_document.py:31](../app/domain/resume_document.py#L31))
- class **`ResumeDocument`** ([app/domain/resume_document.py:43](../app/domain/resume_document.py#L43)) — Versioned source of truth for editing, tailoring, and rendering.
  - `record_revision()` :59
  - `snapshot()` :84 — Return a JSON-serializable, versioned document for storage or export.
- **Imports:** `domain/resume.py`
- **Imported by:** `analysis/resume_normalizer.py`, `analysis/structure_extractor.py`, `rendering/html_renderer.py`, `rendering/layout.py`, `rendering/page_fit.py`, `rendering/template_renderer.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_ats_round_trip.py`, `tests/unit/test_check_parsed_resume.py`, `tests/unit/test_docx_renderer.py`, `tests/unit/test_html_renderer.py`, `tests/unit/test_kept_sections_p83.py`, `tests/unit/test_page_fit.py`, `tests/unit/test_parsing_fixes_p19.py`, `tests/unit/test_project_rewrites.py`, `tests/unit/test_resume_document.py`, `tests/unit/test_resume_model_v2.py`, `tests/unit/test_review_view.py`, `tests/unit/test_template_layout.py`, `tests/unit/test_template_renderer_standalone.py`

### `app/domain/tailoring.py`

**Layer:** Domain models · **Stage:** 6 Plan · **Lines:** 29

- class **`TailoringAction`** ([app/domain/tailoring.py:4](../app/domain/tailoring.py#L4))
- class **`TailoringPlan`** ([app/domain/tailoring.py:25](../app/domain/tailoring.py#L25))
- **Imported by:** `analysis/rewriter.py`, `analysis/tailor_planner.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_new_role.py`, `tests/unit/test_rewriter.py`, `tests/unit/test_tailor_planner.py`

### `app/eval/__init__.py`

**Layer:** Root · **Stage:** — · **Lines:** 2

_Evaluation harness (P4.1): run resume + JD cases through the pipeline and_

- **Tested by:** `tests/unit/test_eval_harness.py`

### `app/eval/__main__.py`

**Layer:** Root · **Stage:** — · **Lines:** 91

_python -m app.eval run [--live] [--tailor] [--case NAME] [--compare BASELINE] [--save PATH]_

- function **`main()`** ([app/eval/__main__.py:20](../app/eval/__main__.py#L20))
- **Imports:** `eval/harness.py`, `eval/judge.py`
- **Tested by:** `tests/unit/test_eval_harness.py`, `tests/unit/test_judge.py`

### `app/eval/golden.py`

**Layer:** Root · **Stage:** 2 Normalize · **Lines:** 49

_Canonical projection of a parsed resume, compared against hand-checked_

- function **`project_resume()`** ([app/eval/golden.py:11](../app/eval/golden.py#L11)) — The parts of a parsed resume a golden file pins down.
- function **`project()`** ([app/eval/golden.py:41](../app/eval/golden.py#L41)) — Parse a file deterministically (no LLM) and project it.
- function **`golden_mismatches()`** ([app/eval/golden.py:47](../app/eval/golden.py#L47)) — Top-level fields where the parse differs from the golden file.
- **Imports:** `analysis/resume_normalizer.py`, `domain/resume.py`, `ingestion/docx.py`, `ingestion/pdf.py`
- **Imported by:** `eval/harness.py`
- **Tested by:** `tests/integration/test_parse_golden.py`

### `app/eval/harness.py`

**Layer:** Root · **Stage:** all · **Lines:** 531

_Run evaluation cases through the pipeline and collect metrics (P4.1)._

- class **`Case`** ([app/eval/harness.py:37](../app/eval/harness.py#L37))
- class **`OfflineLLM`** ([app/eval/harness.py:48](../app/eval/harness.py#L48)) — Stands in for LLMClient when no model should be called: every
  - `is_available()` :55
  - `get_usage_summary()` :58
- class **`_RetryCounter`** ([app/eval/harness.py:64](../app/eval/harness.py#L64))
  - `__init__()` :65
  - `emit()` :69
- function **`load_cases()`** ([app/eval/harness.py:74](../app/eval/harness.py#L74))
- function **`keyword_coverage()`** ([app/eval/harness.py:94](../app/eval/harness.py#L94)) — Share of the JD's keywords found verbatim (whole term, any case) in
- function **`run_case()`** ([app/eval/harness.py:103](../app/eval/harness.py#L103))
- function **`_tailor_metrics()`** ([app/eval/harness.py:194](../app/eval/harness.py#L194))
- function **`attainable_coverage()`** ([app/eval/harness.py:238](../app/eval/harness.py#L238)) — Of the JD keywords written verbatim somewhere in the resume, the share
- function **`_norm_number()`** ([app/eval/harness.py:257](../app/eval/harness.py#L257))
- function **`fabricated_numbers()`** ([app/eval/harness.py:262](../app/eval/harness.py#L262)) — Numbers (with their units) in the tailored resume that the original
- function **`stuffing()`** ([app/eval/harness.py:272](../app/eval/harness.py#L272)) — Signs of keyword stuffing: tailoring pushed the rate above the target
- function **`_docx_text()`** ([app/eval/harness.py:282](../app/eval/harness.py#L282))
- function **`is_content_failure()`** ([app/eval/harness.py:297](../app/eval/harness.py#L297))
- function **`_same_text()`** ([app/eval/harness.py:301](../app/eval/harness.py#L301))
- function **`check_job_details()`** ([app/eval/harness.py:306](../app/eval/harness.py#L306)) — Each job's title, company, dates and bullet count as the file states
- function **`check_must_keep()`** ([app/eval/harness.py:326](../app/eval/harness.py#L326)) — Source phrases that must survive into the rendered file.
- function **`check_expected()`** ([app/eval/harness.py:335](../app/eval/harness.py#L335)) — Compare a run with the case's expected.json; one message per miss.
- function **`_judge()`** ([app/eval/harness.py:404](../app/eval/harness.py#L404)) — Judge one tailored resume (P4.3) and record what the judge cost.
- function **`replay_case()`** ([app/eval/harness.py:415](../app/eval/harness.py#L415)) — Judge the tailored output a previous run saved in replay_dir/<case>/
- function **`run()`** ([app/eval/harness.py:435](../app/eval/harness.py#L435))
- function **`_flatten()`** ([app/eval/harness.py:455](../app/eval/harness.py#L455))
- function **`compare()`** ([app/eval/harness.py:472](../app/eval/harness.py#L472)) — Human-readable differences per case between a report and a baseline.
- function **`_judge_summary()`** ([app/eval/harness.py:500](../app/eval/harness.py#L500))
- function **`summary_lines()`** ([app/eval/harness.py:506](../app/eval/harness.py#L506))
- **Imports:** `analysis/experience.py`, `analysis/jd_analyzer.py`, `analysis/keyword_match.py`, `domain/report.py`, `eval/golden.py`, `eval/judge.py`, `llm/client.py`, `rendering/layout.py`, `services/tailor.py`
- **Imported by:** `eval/__main__.py`
- **Tested by:** `tests/integration/test_arrange.py`, `tests/integration/test_eval_cases.py`, `tests/integration/test_persona_cases.py`, `tests/unit/test_cli_parity.py`, `tests/unit/test_eval_harness.py`, `tests/unit/test_gap_questions.py`, `tests/unit/test_judge.py`, `tests/unit/test_profile_store.py`

### `app/eval/judge.py`

**Layer:** Root · **Stage:** 7 Rewrite, 8 Validate · **Lines:** 109

_LLM-as-judge for the evaluation harness (P4.3)._

- class **`ResumeJudge`** ([app/eval/judge.py:37](../app/eval/judge.py#L37))
  - `__init__()` :38
  - `_ask()` :41
  - `rubric()` :46
  - `prefer()` :51
  - `judge()` :58 — Rubric + position-swapped pairwise for one case. A failed call is
- function **`_prompt()`** ([app/eval/judge.py:27](../app/eval/judge.py#L27))
- function **`judge_client()`** ([app/eval/judge.py:32](../app/eval/judge.py#L32))
- function **`_one_line()`** ([app/eval/judge.py:83](../app/eval/judge.py#L83))
- function **`report_markdown()`** ([app/eval/judge.py:87](../app/eval/judge.py#L87)) — A dated, human-readable judge report for a run.
- **Imports:** `config/settings.py`, `llm/client.py`, `llm/schemas.py`
- **Imported by:** `eval/__main__.py`, `eval/harness.py`
- **Tested by:** `tests/unit/test_judge.py`
- **Prompts:** `llm/prompts/final_review.txt`, `llm/prompts/judge_pairwise.txt`

### `app/ingestion/docx.py`

**Layer:** Ingestion · **Stage:** 1 Ingest · **Lines:** 259

- class **`RawBlock`** ([app/ingestion/docx.py:12](../app/ingestion/docx.py#L12))
- class **`RawDocument`** ([app/ingestion/docx.py:28](../app/ingestion/docx.py#L28))
- class **`DocxParser`** ([app/ingestion/docx.py:36](../app/ingestion/docx.py#L36))
  - `_classify()` :48 — -> (block_type, text without a bullet glyph, whole line bold).
  - `_skills_label_row()` :82 — 'Label: values' for a two-cell row of a skills table, else None.
  - `_text_box_paragraphs()` :109 — Paragraphs inside text boxes anchored in this paragraph (P8.7:
  - `_hyperlinks()` :127 — Targets of every external hyperlink in the body, in rId order
  - `parse()` :138
- **Imports:** `rendering/document_map.py`
- **Imported by:** `analysis/resume_normalizer.py`, `analysis/structure_extractor.py`, `eval/golden.py`, `ingestion/pdf.py`, `services/tailor.py`, `validation/output.py`
- **Tested by:** `tests/integration/test_preserve_rewrite_end_to_end.py`, `tests/unit/test_ats_round_trip.py`, `tests/unit/test_docx_parser.py`, `tests/unit/test_docx_renderer.py`, `tests/unit/test_education_p88.py`, `tests/unit/test_job_lines_p85.py`, `tests/unit/test_kept_sections_p83.py`, `tests/unit/test_layouts_p87.py`, `tests/unit/test_parser_regressions_p42.py`, `tests/unit/test_parsing_fixes_p19.py`, `tests/unit/test_pdf_parser.py`, `tests/unit/test_resume_model_v2.py`, `tests/unit/test_resume_normalizer.py`, `tests/unit/test_stage_h_review.py`, `tests/unit/test_structure_extractor.py`, `tests/unit/test_tailor_resume_flow.py`

### `app/ingestion/ocr.py`

**Layer:** Ingestion · **Stage:** 1 Ingest · **Lines:** 33

- class **`OCREngine`** ([app/ingestion/ocr.py:6](../app/ingestion/ocr.py#L6))
  - `__init__()` :7
  - `is_available()` :15
  - `extract_text_from_image()` :18
- **Imported by:** `ingestion/pdf.py`

### `app/ingestion/pdf.py`

**Layer:** Ingestion · **Stage:** 1 Ingest · **Lines:** 373

- class **`_Line`** ([app/ingestion/pdf.py:41](../app/ingestion/pdf.py#L41)) — One visual text line with the layout facts the parser needs.
- class **`PdfParser`** ([app/ingestion/pdf.py:73](../app/ingestion/pdf.py#L73))
  - `__init__()` :80
  - `_ensure_fitz()` :83
  - `_merge_wrapped_lines()` :91 — Text-only fallback for joining word-wrapped lines: a line is joined
  - `_page_lines()` :112
  - `_attach_right_columns()` :134 — A short, right-aligned run printed on the same row as a left-hand
  - `_split_bullet()` :181 — Return the bullet text without its glyph, or None if not a bullet.
  - `_continues()` :188 — Is `line` a word-wrap continuation of the item ending with `prev`?
  - `_assemble()` :211 — Join continuation lines onto their bullet/paragraph. Each returned
  - `_body_size()` :235
  - `_is_heading()` :242
  - `parse()` :258
- function **`_clean()`** ([app/ingestion/pdf.py:54](../app/ingestion/pdf.py#L54))
- function **`_is_bold_span()`** ([app/ingestion/pdf.py:60](../app/ingestion/pdf.py#L60))
- function **`_join_wrapped()`** ([app/ingestion/pdf.py:64](../app/ingestion/pdf.py#L64)) — Join a wrapped line to the one before it. A line that breaks after
- **Imports:** `ingestion/docx.py`, `ingestion/ocr.py`, `rendering/document_map.py`
- **Imported by:** `eval/golden.py`, `services/tailor.py`, `validation/output.py`
- **Tested by:** `tests/unit/test_layouts_p87.py`, `tests/unit/test_parser_regressions_p42.py`, `tests/unit/test_parsing_fixes_p19.py`, `tests/unit/test_pdf_parser.py`, `tests/unit/test_resume_normalizer.py`, `tests/unit/test_structure_extractor.py`

### `app/llm/client.py`

**Layer:** LLM · **Stage:** 3 JD analysis, 7 Rewrite · **Lines:** 650

- class **`LLMClient`** ([app/llm/client.py:58](../app/llm/client.py#L58)) — Unified client for text generation across three interchangeable providers:
  - `__init__()` :74
  - `is_available()` :143 — Whether the configured provider is reachable AND the configured
  - `_check_available()` :155
  - `_ollama_check()` :162
  - `_groq_check()` :174
  - `_anthropic_check()` :195
  - `_record()` :216
  - `generate()` :234 — Generate text from the LLM using the chat interface.
  - `get_usage_summary()` :264 — Aggregate every LLM call made on this client instance so far
  - `_generate_ollama()` :286
  - `_groq_supports_strict_schema()` :331
  - `_generate_groq()` :335
  - `_split_system()` :419 — The Messages API takes the system prompt as a top-level field,
  - `_anthropic_request()` :426
  - `_anthropic_response()` :463
  - `_generate_anthropic()` :480
  - `_generate_json_anthropic()` :485 — Structured outputs guarantee the response matches the schema, so
  - `generate_json()` :506 — Generate structured JSON conforming to a Pydantic model.
- function **`_requested_wait()`** ([app/llm/client.py:606](../app/llm/client.py#L606)) — How long Groq asks us to wait: the retry-after header, else the
- function **`_retry_after_seconds()`** ([app/llm/client.py:622](../app/llm/client.py#L622)) — Seconds to wait before retrying a 429: the server's `retry-after`
- function **`strict_json_schema()`** ([app/llm/client.py:637](../app/llm/client.py#L637)) — Adapt a Pydantic JSON schema for strict structured-output modes: every
- **Imports:** `config/settings.py`, `llm/schemas.py`, `validation/safety.py`
- **Imported by:** `analysis/jd_analyzer.py`, `analysis/matcher.py`, `analysis/rewriter.py`, `analysis/structure_extractor.py`, `analysis/summary_writer.py`, `analysis/tailor_planner.py`, `api/main.py`, `cli.py`, `eval/harness.py`, `eval/judge.py`, `services/tailor.py`, `scripts/benchmark_model.py`
- **Tested by:** `tests/unit/test_judge.py`, `tests/unit/test_llm_client.py`, `tests/unit/test_rewriter.py`, `tests/unit/test_validation.py`

### `app/llm/schemas.py`

**Layer:** LLM · **Stage:** 3 JD analysis, 7 Rewrite · **Lines:** 98

- class **`LLMResponse`** ([app/llm/schemas.py:4](../app/llm/schemas.py#L4))
- class **`LLMError`** ([app/llm/schemas.py:13](../app/llm/schemas.py#L13)) — Base exception for LLM errors.
- class **`LLMConnectionError`** ([app/llm/schemas.py:18](../app/llm/schemas.py#L18)) — Raised when Ollama server is unreachable.
- class **`LLMTimeoutError`** ([app/llm/schemas.py:23](../app/llm/schemas.py#L23)) — Raised when LLM call exceeds timeout.
- class **`LLMInvalidJSONError`** ([app/llm/schemas.py:28](../app/llm/schemas.py#L28)) — Raised when structured JSON output parsing fails after retries.
- class **`BulletRewriteResult`** ([app/llm/schemas.py:32](../app/llm/schemas.py#L32)) — Structured response for a single bullet rewrite/composition call.
- class **`JDRequirementLine`** ([app/llm/schemas.py:39](../app/llm/schemas.py#L39)) — One JD line the LLM judged to be a candidate requirement, by index.
- class **`JDAnalysisResult`** ([app/llm/schemas.py:46](../app/llm/schemas.py#L46)) — One structured JD analysis call (P1.1). Requirement lines are chosen
- class **`RoleBulletRewrite`** ([app/llm/schemas.py:63](../app/llm/schemas.py#L63)) — One rewritten bullet from a per-role rewrite call (P1.4).
- class **`RoleRewriteResult`** ([app/llm/schemas.py:71](../app/llm/schemas.py#L71)) — All bullets of one role rewritten in a single call (P1.4).
- class **`SummaryResult`** ([app/llm/schemas.py:76](../app/llm/schemas.py#L76)) — A tailored professional summary (P1.5).
- class **`JudgeRubric`** ([app/llm/schemas.py:83](../app/llm/schemas.py#L83)) — LLM-as-judge rubric for one tailored resume (P4.3).
- class **`JudgePairwise`** ([app/llm/schemas.py:95](../app/llm/schemas.py#L95)) — Which of two resume versions is better for the JD (P4.3).
- **Imported by:** `analysis/jd_analyzer.py`, `analysis/rewriter.py`, `analysis/summary_writer.py`, `cli.py`, `eval/judge.py`, `llm/client.py`
- **Tested by:** `tests/unit/test_cli.py`, `tests/unit/test_jd_analyzer_llm.py`, `tests/unit/test_jd_analyzer_v2.py`, `tests/unit/test_judge.py`, `tests/unit/test_llm_client.py`, `tests/unit/test_project_rewrites.py`, `tests/unit/test_rewriter.py`, `tests/unit/test_summary_writer.py`, `tests/unit/test_tailor_resume_flow.py`

### `app/rendering/document_map.py`

**Layer:** Rendering · **Stage:** 1 Ingest, 9 Render · **Lines:** 22

- class **`DocumentLocation`** ([app/rendering/document_map.py:4](../app/rendering/document_map.py#L4))
- class **`DocumentMap`** ([app/rendering/document_map.py:15](../app/rendering/document_map.py#L15))
  - `add_location()` :18
  - `get_location()` :21
- **Imported by:** `ingestion/docx.py`, `ingestion/pdf.py`, `rendering/docx_patcher.py`
- **Tested by:** `tests/unit/test_docx_parser.py`, `tests/unit/test_parsing_fixes_p19.py`, `tests/unit/test_resume_model_v2.py`, `tests/unit/test_structure_extractor.py`

### `app/rendering/docx_patcher.py`

**Layer:** Rendering · **Stage:** 9 Render · **Lines:** 59

- class **`DocxPatcher`** ([app/rendering/docx_patcher.py:9](../app/rendering/docx_patcher.py#L9)) — Apply approved text-only rewrites without rebuilding the source document.
  - `_replace_paragraph_text()` :13
  - `patch()` :26
- **Imports:** `analysis/rewriter.py`, `rendering/document_map.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/integration/test_preserve_rewrite_end_to_end.py`, `tests/unit/test_docx_renderer.py`

### `app/rendering/html_renderer.py`

**Layer:** Rendering · **Stage:** 9 Render · **Lines:** 160

- class **`HtmlResumeRenderer`** ([app/rendering/html_renderer.py:10](../app/rendering/html_renderer.py#L10)) — Render an ATS-safe, printable résumé from the canonical document.
  - `_items()` :13
  - `_meta_line()` :16 — A de-emphasized 'Company · Location' style line under a bolded
  - `_dates()` :25
  - `_experience_entry()` :28
  - `_section()` :54
  - `_other()` :57 — A kept section (P8.3), each line as written.
  - `render()` :74 — Same sections, order and headings as the DOCX template (P2.1).
  - `write_html()` :156
- **Imports:** `domain/resume.py`, `domain/resume_document.py`, `rendering/layout.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/integration/test_preserve_rewrite_end_to_end.py`, `tests/unit/test_html_renderer.py`, `tests/unit/test_kept_sections_p83.py`, `tests/unit/test_parsing_fixes_p19.py`, `tests/unit/test_resume_model_v2.py`, `tests/unit/test_template_layout.py`

### `app/rendering/layout.py`

**Layer:** Rendering · **Stage:** 9 Render · **Lines:** 166

_Shared layout rules for the ATS template (P2.1)._

- function **`section_order_for()`** ([app/rendering/layout.py:38](../app/rendering/layout.py#L38)) — Default order; education moves before experience for someone with
- function **`_place_kept_sections()`** ([app/rendering/layout.py:51](../app/rendering/layout.py#L51)) — Each kept section goes right after the section it followed in the
- function **`other_section()`** ([app/rendering/layout.py:75](../app/rendering/layout.py#L75)) — The kept section an "other:<id>" order entry names, or None.
- function **`ordered_sections()`** ([app/rendering/layout.py:81](../app/rendering/layout.py#L81)) — `order` plus any kept section it doesn't list yet (an order saved
- function **`format_date()`** ([app/rendering/layout.py:87](../app/rendering/layout.py#L87)) — 'August 2024' / 'Aug. 2024' / '08/2024' -> 'Aug 2024'; 'Current' ->
- function **`date_range()`** ([app/rendering/layout.py:122](../app/rendering/layout.py#L122)) — 'Jan 2022 – Present'; one side only when the other is missing. Both
- function **`format_date_text()`** ([app/rendering/layout.py:129](../app/rendering/layout.py#L129)) — A free-text range such as an education's '2016 - 2020' or
- function **`contact_parts()`** ([app/rendering/layout.py:139](../app/rendering/layout.py#L139)) — email | phone | City, Country | linkedin | github | other links.
- function **`display_skills()`** ([app/rendering/layout.py:147](../app/rendering/layout.py#L147)) — At most `max_categories` lines: the first ones as they are (JD-relevant
- function **`output_basename()`** ([app/rendering/layout.py:161](../app/rendering/layout.py#L161)) — First_Last_Resume_<Company>, using only file-name-safe characters.
- **Imports:** `analysis/experience.py`, `domain/resume.py`, `domain/resume_document.py`
- **Imported by:** `eval/harness.py`, `rendering/html_renderer.py`, `rendering/template_renderer.py`, `services/arrange.py`, `services/tailor.py`, `validation/output.py`
- **Tested by:** `tests/unit/test_dates_p86.py`, `tests/unit/test_kept_sections_p83.py`, `tests/unit/test_stage_h_review.py`, `tests/unit/test_template_layout.py`

### `app/rendering/page_fit.py`

**Layer:** Rendering · **Stage:** 9 Render · **Lines:** 243

_Page-fit loop (P2.4): render, count pages, trim, render again._

- class **`FitResult`** ([app/rendering/page_fit.py:44](../app/rendering/page_fit.py#L44))
  - `trimmed()` :52
  - `fits()` :56
- class **`PageFitter`** ([app/rendering/page_fit.py:75](../app/rendering/page_fit.py#L75)) — `render(document, docx_path, out_dir)` writes the DOCX and returns the
  - `__init__()` :80
  - `fit()` :85 — `pinned`: bullet ids, project ids and "interests" the user kept on
  - `_drop_interests()` :133
  - `_trim_bullets()` :140 — Least relevant bullets first, within the per-role minimums; never
  - `_drop_sections()` :176 — Least relevant job sub-section or project, as a whole; never one
  - `_compact()` :216
- function **`measure_pdf()`** ([app/rendering/page_fit.py:60](../app/rendering/page_fit.py#L60)) — (page count, points of the last page used by text below its top margin).
- function **`bullet_height()`** ([app/rendering/page_fit.py:71](../app/rendering/page_fit.py#L71))
- function **`_is_current()`** ([app/rendering/page_fit.py:223](../app/rendering/page_fit.py#L223)) — The first job, and any other job that hasn't ended, keep the larger
- function **`_owner_label()`** ([app/rendering/page_fit.py:230](../app/rendering/page_fit.py#L230)) — "Lakeshore Electric (Journeyman Electrician)" or a project's name, so
- function **`_short()`** ([app/rendering/page_fit.py:241](../app/rendering/page_fit.py#L241))
- **Imports:** `analysis/experience.py`, `domain/resume.py`, `domain/resume_document.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_new_role.py`, `tests/unit/test_page_fit.py`, `tests/unit/test_tailor_resume_flow.py`

### `app/rendering/pdf_converter.py`

**Layer:** Rendering · **Stage:** 9 Render · **Lines:** 78

- class **`PdfConverter`** ([app/rendering/pdf_converter.py:11](../app/rendering/pdf_converter.py#L11))
  - `find_libreoffice_binary()` :12
  - `convert_docx_to_pdf()` :29
- function **`pdf_page_images()`** ([app/rendering/pdf_converter.py:72](../app/rendering/pdf_converter.py#L72)) — Each PDF page as PNG bytes. Shown as images, a preview works in any
- **Imported by:** `api/routes.py`, `services/tailor.py`, `scripts/make_eval_cases.py`
- **Tested by:** `tests/integration/test_preserve_rewrite_end_to_end.py`, `tests/unit/test_ats_round_trip.py`, `tests/unit/test_pdf_converter.py`

### `app/rendering/review_view.py`

**Layer:** Rendering · **Stage:** 7 Rewrite · **Lines:** 110

_What the proposal review screen shows (P3.4, served by the web API since_

- function **`_words()`** ([app/rendering/review_view.py:15](../app/rendering/review_view.py#L15)) — Words, with each line break kept as its own token (skills are lines).
- function **`_keyword_spans()`** ([app/rendering/review_view.py:20](../app/rendering/review_view.py#L20)) — Indexes of words that are part of a JD keyword (case-insensitive,
- function **`_diff()`** ([app/rendering/review_view.py:34](../app/rendering/review_view.py#L34)) — Both texts as words, plus the indexes removed from the original and
- function **`diff_spans()`** ([app/rendering/review_view.py:48](../app/rendering/review_view.py#L48)) — A word diff as data for the web client, which renders it itself: one
- function **`proposal_state()`** ([app/rendering/review_view.py:73](../app/rendering/review_view.py#L73)) — One of PROPOSAL_STATES' keys for a proposal.
- function **`score_breakdown()`** ([app/rendering/review_view.py:84](../app/rendering/review_view.py#L84)) — Per keyword kind: how many found and how much of the rate it earns.
- function **`gap_table()`** ([app/rendering/review_view.py:101](../app/rendering/review_view.py#L101)) — Missing JD keywords, required and heaviest first, and whether a gap
- **Imports:** `domain/report.py`
- **Imported by:** `api/routes.py`
- **Tested by:** `tests/unit/test_review_view.py`

### `app/rendering/template_renderer.py`

**Layer:** Rendering · **Stage:** 9 Render · **Lines:** 310

- class **`TemplateRenderer`** ([app/rendering/template_renderer.py:23](../app/rendering/template_renderer.py#L23)) — Standard single-column, ATS-safe DOCX renderer with support for ResumeDocument.
  - `render_ats_default()` :28 — Render the ATS template (P2.1): A4, single column, Arial,
  - `_add_header()` :66
  - `_add_summary()` :98
  - `_add_experience()` :104
  - `_add_skills()` :139
  - `_add_education()` :150
  - `_add_projects()` :165
  - `_add_certifications()` :188
  - `_add_other()` :194 — A kept section (P8.3): its own heading, each line as written.
  - `_add_achievements()` :205
  - `_add_interests()` :210
  - `_set_document_defaults()` :217 — A4, the template's margins and font, instead of python-docx's
  - `_content_width()` :239
  - `_add_section_heading()` :243 — A section label in the accent color with a rule underneath —
  - `_role_dates()` :258
  - `_add_meta_line()` :261 — 'Company · Location' in italic grey under a title line.
  - `_add_bullets()` :270
  - `_add_title_dates_line()` :275 — Title (bold) on the left, date range right-aligned on the same
  - `_add_bottom_border()` :297 — Adds a single bottom border to a paragraph via raw OOXML — the
- **Imports:** `domain/resume_document.py`, `rendering/layout.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_ats_round_trip.py`, `tests/unit/test_docx_renderer.py`, `tests/unit/test_kept_sections_p83.py`, `tests/unit/test_parsing_fixes_p19.py`, `tests/unit/test_resume_model_v2.py`, `tests/unit/test_template_layout.py`, `tests/unit/test_template_renderer_standalone.py`

### `app/services/arrange.py`

**Layer:** Services · **Stage:** 9 Render · **Lines:** 227

_Arrange and edit before download (P8.13–P8.16)._

- class **`Layout`** ([app/services/arrange.py:30](../app/services/arrange.py#L30))
- function **`_owners()`** ([app/services/arrange.py:45](../app/services/arrange.py#L45))
- function **`default_layout()`** ([app/services/arrange.py:49](../app/services/arrange.py#L49)) — The layout tailoring produced: everything shown, in its current order.
- function **`_ordered()`** ([app/services/arrange.py:59](../app/services/arrange.py#L59)) — Items in `order`; any not listed keep their place after the listed ones.
- function **`apply_layout()`** ([app/services/arrange.py:65](../app/services/arrange.py#L65)) — A copy of `full` arranged as `layout` says. Unknown ids are ignored;
- function **`_had_bullets()`** ([app/services/arrange.py:97](../app/services/arrange.py#L97))
- function **`emptied()`** ([app/services/arrange.py:101](../app/services/arrange.py#L101)) — Jobs and projects the user took every bullet out of.
- function **`section_order()`** ([app/services/arrange.py:107](../app/services/arrange.py#L107)) — The render order: the user's order, then anything it doesn't list.
- function **`notes_for()`** ([app/services/arrange.py:115](../app/services/arrange.py#L115)) — Things worth pointing out about the user's arrangement. Advice only.
- function **`_today()`** ([app/services/arrange.py:143](../app/services/arrange.py#L143))
- function **`_all_text()`** ([app/services/arrange.py:148](../app/services/arrange.py#L148))
- function **`view()`** ([app/services/arrange.py:155](../app/services/arrange.py#L155)) — What the Arrange screen shows: every section with its entries and
- function **`trimmed_items()`** ([app/services/arrange.py:212](../app/services/arrange.py#L212)) — What page-fit removed: bullets (with their job), projects, Interests.
- **Imports:** `analysis/experience.py`, `domain/resume.py`, `rendering/layout.py`
- **Imported by:** `api/routes.py`, `services/tailor.py`
- **Tested by:** `tests/integration/test_arrange.py`

### `app/services/profile_store.py`

**Layer:** Services · **Stage:** 7 Rewrite · **Lines:** 136

_Local profile of facts the user has confirmed (P3.2)._

- class **`ConfirmedFact`** ([app/services/profile_store.py:26](../app/services/profile_store.py#L26))
- class **`Profile`** ([app/services/profile_store.py:33](../app/services/profile_store.py#L33))
- class **`ProfileStore`** ([app/services/profile_store.py:38](../app/services/profile_store.py#L38))
  - `__init__()` :39
  - `load()` :42
  - `save()` :63
  - `record()` :70 — Save the confirmed keywords (and answer text) from gap answers.
  - `known()` :105 — Saved facts for these keywords (case-insensitive), keyed as given.
  - `forget()` :110 — Forget one keyword, or everything when keyword is None. Returns how many were removed.
- class **`MemoryProfileStore`** ([app/services/profile_store.py:123](../app/services/profile_store.py#L123)) — A profile kept in memory, one per web visitor (P5.1): answers are
  - `__init__()` :128
  - `load()` :132
  - `save()` :135
- **Imports:** `config/settings.py`
- **Imported by:** `api/sessions.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_cli_parity.py`, `tests/unit/test_profile_store.py`

### `app/services/run_manager.py`

**Layer:** Services · **Stage:** 10 Report · **Lines:** 40

- class **`RunManager`** ([app/services/run_manager.py:8](../app/services/run_manager.py#L8))
  - `__init__()` :9
  - `create_run()` :12
  - `save_json()` :30
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_api.py`, `tests/unit/test_cli_parity.py`, `tests/unit/test_gap_questions.py`, `tests/unit/test_new_role.py`, `tests/unit/test_profile_store.py`, `tests/unit/test_project_rewrites.py`, `tests/unit/test_skills_tailor.py`, `tests/unit/test_summary_writer.py`, `tests/unit/test_tailor_resume_flow.py`, `tests/unit/test_validation.py`

### `app/services/tailor.py`

**Layer:** Services · **Stage:** all · **Lines:** 1389

- class **`TailorService`** ([app/services/tailor.py:60](../app/services/tailor.py#L60))
  - `__init__()` :61
  - `generate_preview_md()` :94
  - `_patchable()` :140 — Proposals as in-place DOCX patches. A summary proposal targets the
  - `_apply_gap_answers()` :163 — Ticked keywords join the skills section; a typed answer becomes a
  - `_prefill_from_profile()` :211 — Answers confirmed for an earlier JD pre-fill the same questions
  - `_draft_from_answer()` :223 — Polish the candidate's answer into one bullet that may use only
  - `_split_description()` :242 — Pasted role description -> bullet-sized chunks: one per line (list
  - `validate_new_role()` :252 — Check a new job before any work is done; raises ValueError with a
  - `_new_experience()` :277 — An empty job from the "add a job" fields, validated.
  - `_insert_by_date()` :285 — Place a job in date order: current jobs first, then most recent start.
  - `add_new_role()` :298 — Add a job the resume doesn't have yet (P3.3). Each chunk of the
  - `_skills_proposals()` :335 — The skills section with the JD's skills first, when that changes it (P1.6).
  - `_summary_proposals()` :340 — The tailored summary as a proposal, when one was written (P1.5).
  - `_embed()` :345 — Sentence embeddings for the planner, loaded lazily; raises when the
  - `_fit_relevance()` :354 — Planner relevance per bullet for the page-fit loop. Bullets the user
  - `_render_template()` :364 — One template render plus PDF conversion (the page-fit loop's step).
  - `_coverage()` :372 — Content coverage of the rendered DOCX against the uploaded file (P8.2).
  - `_apply_bullet_order()` :399 — Reorder bullets as planned (most relevant first within each
  - `parse_resume()` :414 — File -> (raw document, ResumeDocument, evidence). The deterministic
  - `normalize_raw()` :424
  - `_copy_parsed()` :434 — Deep copies, so a parse kept in UI session state is never mutated.
  - `preview_keyword_match()` :439 — Match rate if these proposals were applied (P3.4 "recalculate"):
  - `apply_parse_corrections()` :462 — Apply the user's fixes from the "Check parsed resume" step (P3.5).
  - `analyze_only()` :559
  - `generate_proposals()` :587 — Generate rewrite proposals without applying them, plus questions
  - `incorporate_user_addition()` :662 — Fold a user-supplied free-text addition (a project, an
  - `tailor_resume()` :741
  - `arrange()` :1257 — Re-render the tailored resume as the user arranged it (P8.13–P8.16):
- function **`_progress()`** ([app/services/tailor.py:49](../app/services/tailor.py#L49)) — A progress reporter that can never break a run (P3.6).
- function **`_hidden_text()`** ([app/services/tailor.py:1353](../app/services/tailor.py#L1353)) — Text of the sections the user hid, so coverage counts it as their choice.
- function **`_merge_usage()`** ([app/services/tailor.py:1380](../app/services/tailor.py#L1380)) — Combine two LLMClient.get_usage_summary() dicts into one.
- **Imports:** `analysis/checklist.py`, `analysis/experience.py`, `analysis/gap_questions.py`, `analysis/jd_analyzer.py`, `analysis/keyword_match.py`, `analysis/matcher.py`, `analysis/resume_normalizer.py`, `analysis/rewriter.py`, `analysis/scoring.py`, `analysis/semantic_matcher.py`, `analysis/skills_tailor.py`, `analysis/structure_extractor.py`, `analysis/summary_writer.py`, `analysis/tailor_planner.py`, `domain/evidence.py`, `domain/job.py`, `domain/report.py`, `domain/resume.py`, `domain/resume_document.py`, `domain/tailoring.py`, `ingestion/docx.py`, `ingestion/pdf.py`, `llm/client.py`, `rendering/docx_patcher.py`, `rendering/html_renderer.py`, `rendering/layout.py`, `rendering/page_fit.py`, `rendering/pdf_converter.py`, `rendering/template_renderer.py`, `services/arrange.py`, `services/profile_store.py`, `services/run_manager.py`, `validation/content_lint.py`, `validation/coverage.py`, `validation/factual.py`, `validation/output.py`, `validation/safety.py`, `validation/structural.py`
- **Imported by:** `api/main.py`, `cli.py`, `eval/harness.py`
- **Tested by:** `tests/integration/test_arrange.py`, `tests/integration/test_coverage_tailor.py`, `tests/integration/test_end_to_end.py`, `tests/unit/test_api.py`, `tests/unit/test_check_parsed_resume.py`, `tests/unit/test_cli.py`, `tests/unit/test_cli_parity.py`, `tests/unit/test_gap_questions.py`, `tests/unit/test_new_role.py`, `tests/unit/test_profile_store.py`, `tests/unit/test_project_rewrites.py`, `tests/unit/test_review_view.py`, `tests/unit/test_skills_tailor.py`, `tests/unit/test_summary_writer.py`, `tests/unit/test_tailor_resume_flow.py`, `tests/unit/test_tailor_service_addition.py`

### `app/validation/content_lint.py`

**Layer:** Validation · **Stage:** 8 Validate · **Lines:** 125

_Content checks on the finished resume (P2.6). Deterministic, no LLM._

- class **`LintIssue`** ([app/validation/content_lint.py:33](../app/validation/content_lint.py#L33))
- class **`ContentReport`** ([app/validation/content_lint.py:39](../app/validation/content_lint.py#L39))
  - `metric_share()` :45
- function **`_short()`** ([app/validation/content_lint.py:49](../app/validation/content_lint.py#L49))
- function **`_is_present()`** ([app/validation/content_lint.py:54](../app/validation/content_lint.py#L54))
- function **`lint()`** ([app/validation/content_lint.py:58](../app/validation/content_lint.py#L58))
- **Imports:** `analysis/experience.py`, `analysis/rewriter.py`, `domain/resume.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_content_lint.py`

### `app/validation/coverage.py`

**Layer:** Validation · **Stage:** 8 Validate · **Lines:** 118

_Content coverage (P8.2): does every line of the uploaded resume reach the_

- class **`CoverageReport`** ([app/validation/coverage.py:53](../app/validation/coverage.py#L53))
  - `pct()` :61
  - `as_dict()` :66
- function **`words()`** ([app/validation/coverage.py:35](../app/validation/coverage.py#L35)) — Comparable words of a line: lowercase, Unicode letters and digits,
- function **`content_coverage()`** ([app/validation/coverage.py:71](../app/validation/coverage.py#L71)) — `blocks`: the source RawBlocks. `heading_texts`: standard section
- function **`docx_text()`** ([app/validation/coverage.py:110](../app/validation/coverage.py#L110)) — All text of a DOCX: body paragraphs and table cells.
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/integration/test_arrange.py`, `tests/unit/test_coverage.py`, `tests/unit/test_kept_sections_p83.py`, `tests/unit/test_stage_h_review.py`

### `app/validation/factual.py`

**Layer:** Validation · **Stage:** 8 Validate · **Lines:** 502

- class **`ClaimCheck`** ([app/validation/factual.py:13](../app/validation/factual.py#L13))
- class **`ValidationResult`** ([app/validation/factual.py:20](../app/validation/factual.py#L20))
- class **`FactualValidator`** ([app/validation/factual.py:32](../app/validation/factual.py#L32)) — Checks that a rewrite adds no facts beyond the resume's evidence.
  - `dropped_facts()` :120 — (dropped factual terms, dropped content words, retention share,
  - `__init__()` :152
  - `extract_numbers()` :164
  - `_stem()` :169 — Crude stemmer so inflections compare equal:
  - `_keys()` :190 — All forms a term can match by: stem plus canonical alias.
  - `_term_keys()` :200
  - `_is_factual()` :216
  - `_positioned_tokens()` :230 — (token, starts_a_sentence) pairs, so the capital of every
  - `_validate_skills()` :239 — The skills section may be reordered and respelled, never extended (P1.6).
  - `_validate_summary()` :251 — A summary may draw on the whole resume (P1.5): every factual term
  - `_owner_prefix()` :307 — 'exp_001_b03' -> 'exp_001_': the job (or project) a bullet belongs to.
  - `_content_tokens()` :312 — Plain words of a text in order, hyphenated words split into parts
  - `_is_plain()` :320
  - `_new_words()` :325 — Plain words a rewrite adds (P8.9): (borrowed from the JD only,
  - `_words_from_elsewhere()` :344 — Runs of consecutive plain words that the resume uses only under
  - `validate_proposal()` :365
- **Imports:** `analysis/rewriter.py`, `analysis/skills_tailor.py`, `analysis/terminology.py`, `domain/evidence.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_fact_check_p89.py`, `tests/unit/test_skills_tailor.py`, `tests/unit/test_summary_writer.py`, `tests/unit/test_validation.py`

### `app/validation/output.py`

**Layer:** Validation · **Stage:** 8 Validate · **Lines:** 150

- class **`OutputQAValidator`** ([app/validation/output.py:7](../app/validation/output.py#L7))
  - `validate_docx()` :8
  - `validate_pdf()` :30
  - `round_trip()` :63 — Re-parse a rendered DOCX / PDF the way an ATS would (our own
- **Imports:** `analysis/resume_normalizer.py`, `ingestion/docx.py`, `ingestion/pdf.py`, `rendering/layout.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/integration/test_end_to_end.py`, `tests/integration/test_preserve_rewrite_end_to_end.py`, `tests/unit/test_ats_round_trip.py`, `tests/unit/test_pdf_converter.py`

### `app/validation/safety.py`

**Layer:** Validation · **Stage:** 3 JD analysis · **Lines:** 79

- class **`SafetyGuard`** ([app/validation/safety.py:14](../app/validation/safety.py#L14))
  - `strip_invisible()` :38
  - `sanitize()` :41 — Sanitize JD text by escaping system prompt injection attempts.
  - `sanitize_untrusted()` :50 — Clean resume / user text before it goes into a prompt: strip
  - `guard_messages()` :60 — A copy of chat messages with user content sanitised and the
- **Imported by:** `llm/client.py`, `services/tailor.py`
- **Tested by:** `tests/unit/test_validation.py`

### `app/validation/structural.py`

**Layer:** Validation · **Stage:** 8 Validate · **Lines:** 22

- class **`StructuralValidator`** ([app/validation/structural.py:4](../app/validation/structural.py#L4))
  - `validate()` :5
- **Imports:** `domain/resume.py`
- **Imported by:** `services/tailor.py`
- **Tested by:** `tests/unit/test_validation.py`

## 4. Dependency diagram

Arrows point from importer to imported module (app code only; domain models omitted for readability, since almost everything imports them).

```mermaid
flowchart LR
  subgraph Analysis[Analysis]
    analysis_change_proposal[change_proposal]
    analysis_checklist[checklist]
    analysis_experience[experience]
    analysis_gap_questions[gap_questions]
    analysis_jd_analyzer[jd_analyzer]
    analysis_keyword_match[keyword_match]
    analysis_matcher[matcher]
    analysis_resume_normalizer[resume_normalizer]
    analysis_rewriter[rewriter]
    analysis_scoring[scoring]
    analysis_semantic_matcher[semantic_matcher]
    analysis_skills_tailor[skills_tailor]
    analysis_structure_extractor[structure_extractor]
    analysis_summary_writer[summary_writer]
    analysis_tailor_planner[tailor_planner]
    analysis_terminology[terminology]
  end
  subgraph Config[Config]
    config_settings[settings]
  end
  subgraph Entrypoints[Entry points]
    cli[cli]
  end
  subgraph Ingestion[Ingestion]
    ingestion_docx[docx]
    ingestion_ocr[ocr]
    ingestion_pdf[pdf]
  end
  subgraph LLM[LLM]
    llm_client[client]
    llm_schemas[schemas]
  end
  subgraph Rendering[Rendering]
    rendering_document_map[document_map]
    rendering_docx_patcher[docx_patcher]
    rendering_html_renderer[html_renderer]
    rendering_layout[layout]
    rendering_page_fit[page_fit]
    rendering_pdf_converter[pdf_converter]
    rendering_review_view[review_view]
    rendering_template_renderer[template_renderer]
  end
  subgraph Root[Root]
    eval___main__[__main__]
    eval_golden[golden]
    eval_harness[harness]
    eval_judge[judge]
  end
  subgraph Services[Services]
    services_arrange[arrange]
    services_profile_store[profile_store]
    services_run_manager[run_manager]
    services_tailor[tailor]
  end
  subgraph Validation[Validation]
    validation_content_lint[content_lint]
    validation_coverage[coverage]
    validation_factual[factual]
    validation_output[output]
    validation_safety[safety]
    validation_structural[structural]
  end
  subgraph WebAPI[Web API]
    api_forms[forms]
    api_main[main]
    api_routes[routes]
    api_sessions[sessions]
  end
  analysis_checklist --> analysis_experience
  analysis_gap_questions --> analysis_keyword_match
  analysis_jd_analyzer --> analysis_terminology
  analysis_jd_analyzer --> llm_client
  analysis_jd_analyzer --> llm_schemas
  analysis_keyword_match --> analysis_gap_questions
  analysis_keyword_match --> analysis_resume_normalizer
  analysis_keyword_match --> analysis_terminology
  analysis_matcher --> analysis_terminology
  analysis_matcher --> llm_client
  analysis_resume_normalizer --> ingestion_docx
  analysis_rewriter --> analysis_change_proposal
  analysis_rewriter --> llm_client
  analysis_rewriter --> llm_schemas
  analysis_semantic_matcher --> config_settings
  analysis_skills_tailor --> analysis_change_proposal
  analysis_skills_tailor --> analysis_keyword_match
  analysis_structure_extractor --> analysis_resume_normalizer
  analysis_structure_extractor --> ingestion_docx
  analysis_structure_extractor --> llm_client
  analysis_summary_writer --> analysis_change_proposal
  analysis_summary_writer --> analysis_experience
  analysis_summary_writer --> analysis_rewriter
  analysis_summary_writer --> llm_client
  analysis_summary_writer --> llm_schemas
  analysis_tailor_planner --> analysis_keyword_match
  analysis_tailor_planner --> llm_client
  api_forms --> config_settings
  api_main --> api_routes
  api_main --> api_sessions
  api_main --> config_settings
  api_main --> llm_client
  api_main --> services_tailor
  api_routes --> analysis_jd_analyzer
  api_routes --> api___init__
  api_routes --> api_sessions
  api_routes --> rendering_pdf_converter
  api_routes --> rendering_review_view
  api_routes --> services_arrange
  api_sessions --> services_profile_store
  cli --> analysis_gap_questions
  cli --> llm_client
  cli --> llm_schemas
  cli --> services_tailor
  eval___main__ --> eval_harness
  eval___main__ --> eval_judge
  eval_golden --> analysis_resume_normalizer
  eval_golden --> ingestion_docx
  eval_golden --> ingestion_pdf
  eval_harness --> analysis_experience
  eval_harness --> analysis_jd_analyzer
  eval_harness --> analysis_keyword_match
  eval_harness --> eval_golden
  eval_harness --> eval_judge
  eval_harness --> llm_client
  eval_harness --> rendering_layout
  eval_harness --> services_tailor
  eval_judge --> config_settings
  eval_judge --> llm_client
  eval_judge --> llm_schemas
  ingestion_docx --> rendering_document_map
  ingestion_pdf --> ingestion_docx
  ingestion_pdf --> ingestion_ocr
  ingestion_pdf --> rendering_document_map
  llm_client --> config_settings
  llm_client --> llm_schemas
  llm_client --> validation_safety
  rendering_docx_patcher --> analysis_rewriter
  rendering_docx_patcher --> rendering_document_map
  rendering_html_renderer --> rendering_layout
  rendering_layout --> analysis_experience
  rendering_page_fit --> analysis_experience
  rendering_template_renderer --> rendering_layout
  services_arrange --> analysis_experience
  services_arrange --> rendering_layout
  services_profile_store --> config_settings
  services_tailor --> analysis_checklist
  services_tailor --> analysis_experience
  services_tailor --> analysis_gap_questions
  services_tailor --> analysis_jd_analyzer
  services_tailor --> analysis_keyword_match
  services_tailor --> analysis_matcher
  services_tailor --> analysis_resume_normalizer
  services_tailor --> analysis_rewriter
  services_tailor --> analysis_scoring
  services_tailor --> analysis_semantic_matcher
  services_tailor --> analysis_skills_tailor
  services_tailor --> analysis_structure_extractor
  services_tailor --> analysis_summary_writer
  services_tailor --> analysis_tailor_planner
  services_tailor --> ingestion_docx
  services_tailor --> ingestion_pdf
  services_tailor --> llm_client
  services_tailor --> rendering_docx_patcher
  services_tailor --> rendering_html_renderer
  services_tailor --> rendering_layout
  services_tailor --> rendering_page_fit
  services_tailor --> rendering_pdf_converter
  services_tailor --> rendering_template_renderer
  services_tailor --> services_arrange
  services_tailor --> services_profile_store
  services_tailor --> services_run_manager
  services_tailor --> validation_content_lint
  services_tailor --> validation_coverage
  services_tailor --> validation_factual
  services_tailor --> validation_output
  services_tailor --> validation_safety
  services_tailor --> validation_structural
  validation_content_lint --> analysis_experience
  validation_content_lint --> analysis_rewriter
  validation_factual --> analysis_rewriter
  validation_factual --> analysis_skills_tailor
  validation_factual --> analysis_terminology
  validation_output --> analysis_resume_normalizer
  validation_output --> ingestion_docx
  validation_output --> ingestion_pdf
  validation_output --> rendering_layout
```

## 5. Configuration keys

From `app/config/settings.py`; each can be overridden by the env var of the same name in `.env`.

| Env var | Type | Default |
|---|---|---|
| `LLM_PROVIDER` | str | `'ollama'` |
| `LLM_HOST` | str | `'http://localhost:11434'` |
| `LLM_MODEL` | str | `'qwen3:4b'` |
| `LLM_TEMPERATURE` | float | `0.1` |
| `LLM_TIMEOUT_SECONDS` | int | `180` |
| `MAX_CONTEXT_TOKENS` | int | `12000` |
| `STRICT_FACTUAL_MODE` | bool | `True` |
| `GROQ_API_KEY` | str | `''` |
| `GROQ_MODEL` | str | `'openai/gpt-oss-120b'` |
| `GROQ_BASE_URL` | str | `'https://api.groq.com/openai/v1'` |
| `GROQ_FORCE_IPV4` | bool | `True` |
| `ANTHROPIC_API_KEY` | str | `''` |
| `ANTHROPIC_MODEL` | str | `'claude-opus-5-5'` |
| `JUDGE_PROVIDER` | str | `'groq'` |
| `JUDGE_MODEL` | str | `'qwen/qwen3.8-27b'` |
| `PROFILE_PATH` | str | `os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'profile', 'facts.json')` |
| `API_SESSION_TTL_MINUTES` | int | `60` |
| `API_MAX_UPLOAD_MB` | int | `5` |
| `API_RATE_LIMIT_PER_HOUR` | int | `30` |
| `SEMANTIC_MATCH_ENABLED` | bool | `True` |
| `SEMANTIC_MATCH_MODEL` | str | `'all-MiniLM-L6-v2'` |
| `SEMANTIC_MATCH_THRESHOLD` | float | `0.58` |

## 6. Prompts

| Prompt file | Loaded by |
|---|---|
| `final_review.txt` | `app/eval/judge.py` |
| `jd_analysis.txt` | `app/analysis/jd_analyzer.py` |
| `judge_pairwise.txt` | `app/eval/judge.py` |
| `rewrite_bullet.txt` | `app/analysis/rewriter.py` |
| `rewrite_role.txt` | `app/analysis/rewriter.py` |
| `summary.txt` | `app/analysis/summary_writer.py` |

## 7. Gaps: untested and unmapped modules

**No test file imports these directly** (they may still be exercised indirectly):

- `app/analysis/terminology.py`
- `app/api/forms.py`
- `app/ingestion/ocr.py`

**Not imported by any app code** (possibly dead code, or only used by tests/scripts):

- `app/api/forms.py`
- `app/eval/__main__.py`

**Not in `STAGE_MAP`** (add them in `scripts/update_docs.py`):

- none

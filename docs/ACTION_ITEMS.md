# Action Items — Best Tailored Resume per JD

_Living tracker. Update an item's **Status** in the same commit that changes it; add a short note (commit subject or
what's left). Last updated: 2026-09-30 (strategy revised after the real-resume run)._

**Goal:** every resume + JD run produces the best possible tailored resume: an accurate match score, strong
JD-aligned rewrites, a Novoresume-style ATS layout that fits the right length, and nothing fabricated.

**Status legend:** ⬜ Not started · 🟡 In progress · ✅ Done · ⛔ Blocked · ➖ Dropped

## Progress

| Phase | Items | ✅ | 🟡 | ⬜ |
|---|---|---|---|---|
| 0: Make the LLM path work | 10 | 10 | 0 | 0 |
| 1: Content quality | 14 | 13 | 0 | 1 |
| 2: Template, ATS, page-fit | 6 | 0 | 1 | 5 |
| 3: Gap questions + UX | 6 | 1 | 0 | 5 |
| 4: Evaluation harness | 3 | 1 | 0 | 2 |
| **Total** | **39** | **25** | **1** | **13** |

## Decisions (fixed by the user, 2026-09-30)

| Topic | Decision |
|---|---|
| Length | Auto by experience: 1 page under 8 years, 2 pages above. Trim the least JD-relevant bullets to fit |
| Page / dates | A4, "Jan 2022 – Present" (India / Asia / Europe standard) |
| Layout | Clean ATS single column following Novoresume's layout conventions (our own implementation, not their assets or text) |
| Gaps | Suggest-and-confirm: the tool asks, and drafts only from the user's answer. Never fabricate |
| Confirmed facts | Saved locally (`data/profile/facts.json`, gitignored) and reused across JDs |
| LLM | **Groq free tier only** (`openai/gpt-oss-120b`), with no paid APIs (decided 2026-09-30). The Claude provider (P0.1) stays in the code but is shelved: not used, not even as a fallback. Claude Pro does not include API access |

---

## Implementation strategy (revised 2026-09-30 after the real-resume run)

The real-resume run showed the biggest problem isn't rewriting: **the tool misreads its inputs.** The resume PDF was
parsed wrongly (name, jobs, bullets, skills, education) and the JD was split into fragments. So the work is ordered
**inputs → measurement → content → output → extras**. Each stage ends with a gate: re-run the user's resume against the
FOX JD and compare with the baseline. The phase tables below stay the catalogue; this is the order to work through them.

| Stage | Goal | Items (in order) | Exit gate |
|---|---|---|---|
| **A. Read inputs correctly** | The resume and JD are understood exactly | P1.11 → P1.12 → P1.13 → P1.9 → P1.1 → P3.5 | The user's resume parses 100% correctly against a hand-checked golden file (kept locally, never committed). An anonymized replica PDF of the same layout is committed as a test fixture. The FOX JD yields title, company and clean must-have / nice-to-have lists |
| **B. Measure truthfully** | A score you can trust, and a way to prove improvement | P4.1 → P1.2 | The score for this resume vs the FOX JD is plausible and explained by a matched/missing keyword table; baseline re-recorded |
| **C. Better content** | Every relevant bullet improved, nothing invented, nothing lost | P1.3 → P1.4 → P1.14 → P1.5 → P1.6 → P1.7 → P3.1 | All relevant bullets considered (not just 3 of 13); ≤ ~8 LLM calls per run (fits the Groq free tier without 429s); zero fabrication; no information dropped; harness metrics up vs baseline |
| **D. Output** | A Novoresume-style A4 resume at the right length | P2.1 → P2.2 → P2.3 → P2.4 → P2.5 → P2.6 | This resume (3.6 years) renders as 1 A4 page with roles and projects laid out correctly; ATS round-trip passes |
| **E. Extras & polish** | Convenience and full evaluation | P3.2, P3.3, P3.4, P3.6, P1.10, P4.2, P4.3 | Full eval set green |

**Privacy:** the user's resume and its golden file live in `data/eval/private/` (gitignored). Committed tests use an
anonymized replica of the layout.

---

## Phase 0: Make the LLM path work, stop silent failures

**Exit gate:** a run on the real resume + a real JD shows rewrites that actually change; baseline metrics recorded (P4.1).

**Gate status (2026-09-30):** 🟡 Live Groq verified: `check-llm` OK (0.7 s); a full fixture run gave 2/2 genuinely rewritten bullets, 8 calls, ~8.6K tokens. Found and fixed: gpt-oss emits non-breaking spaces/hyphens ("50 M"), which broke the number check. Validator fixed in P1.8: the same live run now keeps 2/2 rewrites.

**After Stage A (2026-09-30, `python -m app.eval run --live --tailor --case real-fox`):** parse = golden match; JD 21 requirements / 4 preferred (LLM); score 0.0 (whole-line requirements never match the sentence matcher, F12); 7/28 JD keywords verbatim in the resume; 0 rewrites (the planner only rewrites matched bullets, F13); 8 LLM calls, 20.6K tokens, 4 × 429; 2 pages. → Stage B.

**After Stage B (2026-09-30):** parse = golden match; JD 21 requirements / 4 preferred; keyword match rate **29.3%** (8 matched: ML, Databricks, MLOps, Python, LightGBM, Spark via PySpark, AWS, feature stores; missing incl. PyTorch, MLflow, A/B, NDCG, LLMs, FAISS, Kafka, title); 0 rewrites (planner, P1.3); 6 LLM calls, 10.5K tokens, 7 × 429; 2 pages.

**Real-resume baseline (2026-09-30, user's PDF + FOX "SDE L2 / Senior Engineer, ML" JD, Groq gpt-oss-120b):** score 8.0 → 7.1; 3 rewrites proposed, 3 PASS; 5 suggestions (all invent metrics, e.g. "NDCG +12%"); 19 LLM calls, 28.6K tokens, 69 s, 4 rate-limit (429) retries; output 2 pages. **The output is unusable because of PDF parsing (P1.9):** the name was read as a project heading, the company became "Professional Experience" / title "Role", project headings became bullets, `●` glyphs and wrapped lines leaked through, skills/education were garbled, and certifications were filed as interests. JD analysis (P1.1): no title/company, junk requirements from "and"-splitting, and "Nice To Have" items marked required. → **P1.9 and P1.1 moved to the front of Phase 1.** Phase 0's own goal (a working LLM path) is met ✅.

| ID | Action | Files | Resolves | Status | Notes |
|---|---|---|---|---|---|
| P0.1 | Add a Claude provider: `LLM_PROVIDER=anthropic`, `ANTHROPIC_MODEL=claude-opus-5-5`; `client.messages.parse()` / `output_config.format` against the `app/llm/schemas.py` models; explicit `effort`; handle `stop_reason` refusal / max_tokens; keep `usage_log`. Add the dependency, `.env.example` keys and a privacy note | `app/llm/client.py`, `pyproject.toml`, `.env.example`, `ARCHITECTURE.md` | F1, F5, F6 | ✅ | `anthropic` 1.9 SDK; `beta.messages.parse` with Pydantic `output_format`, `effort` via `output_config`, no temperature, server-side refusal fallback (`fallbacks: "default"`); refusal/max_tokens raise. Mock-tested; **live check pending the user's API key** (P0.10) |
| P0.2 | Provider-aware model picker: never pass an Ollama name to Groq/Claude; warning text per provider | `app/ui.py:137-142,201,285-293,387` | F1, F31 | ✅ | Sidebar shows the configured provider and only its models (configured default first); error banner gives the real reason + a provider-specific fix hint |
| P0.3 | One cached health check per run that verifies the model exists; remove per-call `is_available()` | `client.py:95-120`, `rewriter.py:41,98`, `jd_analyzer.py:140`, `tailor.py:157` | F1, F4 | ✅ | `is_available()` cached per client (one check per run); Groq check now verifies the model id exists; `last_error` explains why (used by P0.4 UI) |
| P0.4 | Visible failures: rewrite status (ok / llm_error / rejected / unchanged) + error on `ChangeProposal`; UI banner; save usage in `generate_proposals` | `rewriter.py`, `change_proposal.py`, `tailor.py:122-159`, `ui.py` | F3, F34 | ✅ | `rewrite_bullet_with_status` → ok / unchanged / llm_unavailable / llm_error stored on each proposal; banner "N of M rewrites failed: reason" + per-bullet ❌ note; proposal-stage usage merged into `llm_usage.json` |
| P0.5 | Groq fallback robustness: 429 `retry-after` backoff, strict `json_schema` for gpt-oss | `client.py:_generate_groq`, `generate_json` | F5, F6 | ✅ | 429 → honour `retry-after` (≤30 s, 3 retries); gpt-oss uses strict `json_schema` + `reasoning_effort` |
| P0.6 | Move the `ollama.py` stub into `tests/conftest.py` so it stops shadowing the real package | `/ollama.py`, `tests/conftest.py` | F2 | ✅ | Stub deleted; no shim needed: tests `@patch("ollama.Client")` on the real package (0.6.2), whose responses are `.get()`-compatible |
| P0.7 | Skip planner + rewriter when proposals are pre-approved | `tailor.py:298-311` | F7 | ✅ | Deterministic planner still runs (for plan.json); `execute_plan` skipped with pre-approved proposals. Test asserts it isn't called |
| P0.8 | Strict mode decides before rendering; `changes.md` matches the rendered output; remove duplicate and dead writes | `tailor.py:391-539` | F8, F33 | ✅ | All-or-nothing rollback before render; changes.md appends one summary under the kept progress log; dead code removed. UI default switched to **off** until P1.8 (the over-strict validator would otherwise withhold nearly every run). Also added `tests/conftest.py`: tests were making live Groq calls via `.env` (suite 47–80 s → 17 s) |
| P0.9 | Quick fixes: keyword regex; `criticality` from priority + "perfect match = 100" test; numeric pattern covers 2M / 10x / 40K / $3.5M / 1,000+ / 5+ years | `jd_analyzer.py:47,239`, `scoring.py`, `factual.py:25` | F9, F10, F16 | ✅ | Score renormalised over non-empty buckets (perfect match = 100); keyword stopgap keeps only technical terms (C++, Node.js, AWS…); numbers include unit suffixes. +9 tests |
| P0.10 | `python -m app.cli check-llm`: one live structured call that prints provider, model, latency and tokens | `app/cli.py` | F1 | ✅ | `python -m app.cli check-llm [--provider X --model Y]` → exit 0 on a valid structured reply; clear reason otherwise |

## Phase 1: Content quality

| ID | Action | Files | Resolves | Status | Notes |
|---|---|---|---|---|---|
| P1.1 | JD analysis v2: one structured call returns title, seniority, min years, hard skills, soft skills, must-have / nice-to-have, education, certs, each with a verbatim JD span (code drops anything not found in the JD). Frequency counted in code. No splitting on "and". Heuristic fallback stays | `jd_analyzer.py`, `domain/job.py`, `prompts/jd_analysis.txt` | F9, F11, F44–F47 | ✅ | One `JDAnalysisResult` call over all numbered lines (replaces line selection): title, company, seniority, min/max years, requirement lines by index with priority + category, hard/soft skills, education, certs. Verbatim guard: every string must occur in the JD (the JD's own spelling is kept), years must appear in the text, otherwise the deterministic value stands. Requirements are whole lines (no "and"-splitting) with `source_spans`. Deterministic side: title/company from "X is looking for a <title> to join", seniority from title, years regex, headings = known patterns / ALL-CAPS / short known-section lines, "Nice To Have, But Not Required" → preferred, intro prose skipped. Keywords = verified hard skills + certs, topped up with technical terms from requirement lines only (no heading/company/team words), ranked by `keyword_counts` (counted in code). FOX JD live: 1 call, ~5K tokens, 6 s; title/company/senior/3–7 years right, 21–22 whole-line requirements, 4 preferred |
| P1.2 | Jobscan-style match rate as the headline score: keyword-level, weights hard skills > title > education/certs > soft skills, required ×1.5. Evidence strength becomes secondary. Target band 75–85% | `matcher.py`, `scoring.py`, `domain/report.py` | F10, F12 | ✅ | New `analysis/keyword_match.py`: one row per JD keyword (hard skills 3, title 2, education/certs 1.5, soft 1; ×1.5 when the keyword is in a required line) with found / where / JD count; rate = weighted share found. Matching is alias-aware (ML = machine learning), plural-insensitive, whole-token (R ≠ React, ML ≠ MLflow), with implied terms (PySpark → Spark) and multi-word terms allowed within one sentence; title gets partial credit from role titles / headline. Headline score everywhere (analyze, proposals, before/after tailoring); the old requirement score stays as `evidence_score`. UI: rate vs 75–85% band + matched/missing table (analysis, proposal review, results); `changes.md` gets a keyword table. `tailor_resume(job_desc=…)` reuses the proposal-time JD analysis (one fewer call; before/after rates now use the same keywords) |
| P1.3 | Planner v2: relevance score per bullet, reorder within each role, trim candidates; rewriter gets only the relevant requirements + allowed keywords | `tailor_planner.py`, `domain/tailoring.py` | F13 | ✅ | Relevance 0–1 per bullet = ½ weighted JD keywords already in the bullet (same lookup as the match rate) + ½ similarity to its closest requirement (local embeddings, token overlap fallback), +0.2 for a deterministic requirement match. REWRITE for every bullet ≥ 0.15 (not just matched ones), else KEEP + `trim_candidate`. Each action carries its top-3 requirement ids and its allowed keywords (JD keywords the bullet or its sub-heading already contains). `plan.bullet_order`: most relevant first within each sub-heading, applied in template mode. Real resume: 10 of 12 bullets selected (was 0) |
| P1.4 | Rewrite v2, one call per role: strong verbs with no repeats, XYZ phrasing only with existing metrics, ≤28 words, JD spelling, no pronouns or buzzwords, never add numbers; returns `keywords_used` + `evidence_ids` | `rewriter.py`, `prompts/rewrite_role.txt`, `llm/schemas.py` | F14 | ✅ | `LLMRewriter.rewrite_role()` + `RoleRewriteResult`: all REWRITE bullets of a job in one call, each with its closest requirements and allowed keywords. Prompt: lead with the JD-relevant work, reuse the requirement's wording only for work the bullet describes, ≤28 words, no repeated opening verbs / pronouns / buzzwords, keep every tool, number and specific detail. Unknown / duplicate ids ignored, `keywords_used` filtered to allowed ones present, punctuation-only edits count as unchanged, a failed call marks each bullet `llm_error` with the reason. Real resume: rewrite step 1 call (was 1 per bullet), 10/10 changed, all numbers and tools kept, requirement wording used where the bullet describes the same work |
| P1.5 | Summary tailoring: years computed in code, real title, top evidenced JD skills, one real metric; validated | new `analysis/summary_writer.py`, `tailor.py`, `ui.py` | F18 | ✅ | `SummaryWriter.facts()` (code): most recent title, years from role dates (`analysis/experience.py`, overlaps merged, "4+ years"), up to 6 JD skills the keyword matcher found, bullets with real numbers, project names. One call (`prompts/summary.txt`, `SummaryResult`) phrases 3 sentences ≤ 60 words; > 70 words is dropped. Proposal `kind="summary"` in the review list; validated against the whole resume (terms must appear in it or in the allowed facts: years, titles, projects, verified skills; numbers must come from it); sentence-initial capitals no longer read as proper nouns. Applied to `resume.summary` + its evidence, rolled back by Strict Mode, patched into the summary paragraph(s) in PRESERVE mode. Real resume: PASS, 47 words, 4+ years (the resume says 3.6), JD spelling ("Spark" for PySpark) |
| P1.6 | Skills tailoring (deterministic): reorder by JD relevance, JD spelling via the alias map | new `analysis/skills_tailor.py` | F18 | ✅ | No LLM. JD skills first within each category (ranked with the match-rate lookup, so PySpark counts as the JD's "Spark"), the category with the most JD weight on top; renamed to the JD spelling only when it's the same term (case / plural / alias: Numpy → NumPy), never PySpark → Spark. Offered as a `kind="skills"` proposal, editable as "Category: a, b" lines; the validator rejects any skill not already on the resume. Applied in template mode (skipped for an in-place DOCX patch), rolled back by Strict Mode. Also fixed a P1.11 split: "Frameworks & Tools:" was cut into a junk "Frameworks &" category |
| P1.7 | Rewrite project bullets through the same flow | `tailor_planner.py`, `rewriter.py`, `tailor.py` | F18 | ✅ | Planner scores `resume.projects` bullets too (project name as context, `target_section="projects"`, order within each project). Rewriter sends all REWRITE project bullets in one extra call (`rewrite_role(None, items, header=…)`, project name as sub-heading). `tailor_resume` applies, reorders and rolls back project bullets like job bullets; validation already covered project evidence. Projects inside a job (the user's layout) were already handled as sub-headings in P1.12 |
| P1.8 | Validator v2: PASS / NEEDS_CONFIRM / REJECT; action-verb allowlist + alias-aware; reject new numbers and unevidenced tools or orgs; keep the user's own edits (logged as user-attested) | `factual.py`, `tailor.py:321-334`, `ui.py` | F15, F16, F17 | ✅ | Ordinary words pass; factual-looking terms (tools, acronyms, proper nouns, JD skills, scope claims like "led a team") must be in this bullet's source (PASS) or elsewhere in the resume (NEEDS_CONFIRM) or it's REJECT. Alias- and inflection-aware. Verdicts shown per proposal before Apply; user-edited text kept as user-attested. Live Groq fixture: 0/2 → 2/2 rewrites survive. Strict Mode stays opt-in |
| P1.9 | Parsing fixes: LinkedIn/GitHub links (incl. DOCX hyperlinks), `headline` field, no placeholder rendering, handle "Previously:", DOCX walked in document order | `resume_normalizer.py`, `domain/resume.py`, `ingestion/docx.py`, `ingestion/pdf.py` | F21–F25 | ✅ | Links from DOCX hyperlink relationships, PDF link annotations and URLs written in the header, deduped, mailto:/tel: excluded (mailto fills a missing email); `Candidate.display_links()` renders `linkedin.com/in/x`. `Candidate.headline`: a short non-contact line under the name (not a location, sentence or "LinkedIn \| Email" placeholder); rendered in DOCX/HTML/preview. DOCX walked with `iter_inner_content()` (tables in place, correct section), merged cells read once, table-cell paragraphs classified like body ones, Word page-header contact read. A short plain line directly above a dated line is a company. Short header lines no longer count as stray evidence (so they don't trigger P1.13). Placeholder company/title and "Previously:" were already removed in P1.12 |
| P1.11 | **Layout-aware PDF parsing:** name = largest font on page 1; join bullet continuation lines by indent (not "starts lowercase"); strip `●` glyphs + zero-width spaces; detect headings by uppercase/known section names even when not bold; read right-aligned columns on the same line as location/dates; split multi-category skill lines (`Languages: … Frameworks: …`); route labelled `Certifications:` / `Interests:` lines | `ingestion/pdf.py`, `resume_normalizer.py` | F36, F38–F43 | ✅ | Parser reads `get_text("dict")`: name = largest font (≥1.3× body), bullets joined by indent (bold continuations too), paragraphs joined when a line reaches the right margin, lowercase rule kept as fallback; never joins across a font-size jump or onto a `Label:` line. Right-aligned runs on the same row and 3+ space gaps become a tab (right column). `●`, ZWSP, NBSP, soft hyphen cleaned. `RawBlock` gains `bold` / `font_size`, `RawDocument` gains `links`. Anonymized fixture `tests/fixtures/resumes/replica_layout.pdf` (+ generator script). Real resume: name, contact, summary, 13 complete bullets, skills, education, certs/interests all read right; roles and project sub-sections need P1.12 |
| P1.12 | **Resume model v2:** a company can hold several roles (title + dates each, e.g. Data Scientist II / I); a role can hold project sub-sections with their own bullets; certifications become their own field. Normalizer, evidence ledger and both renderers updated | `domain/resume.py`, `resume_normalizer.py`, `rendering/*` | F37, F42 | ✅ | `Role` model + `Experience.roles` (most recent first; `title`/dates mirror roles[0]); `ResumeBullet.group` = sub-heading (project) inside a job; helpers `all_roles()` / `bullet_groups()`. Normalizer: a heading-like line followed by a dated line is a company, otherwise a sub-heading; title-before-company order handled; a new title after bullets stays at the same company; empty company/title instead of placeholders (renderers skip them); the "Previously:" note is gone (F23). Fixed `DATE_PATTERN` matching "Market"/"Decision"/"Junior" as months. Certifications were already a field; P1.11 fixed their routing. Evidence text carries the sub-heading. DOCX + HTML + preview render roles and sub-headings. Golden-file test (`tests/integration/test_parse_golden.py`): replica committed, the user's resume passes locally (private) |
| P1.13 | **LLM-assisted structure extraction with a verbatim guard:** when the deterministic parse looks wrong (no name, placeholder company/title, orphan headings), ask Groq to map numbered lines to resume fields **by index** (same pattern as JD line selection), so every value is still copied verbatim from the file | new `analysis/structure_extractor.py`, `resume_normalizer.py` | F36, F37 | ✅ | `StructureExtractor.problems()` flags: no/odd name, bullets but no jobs, a job without company/title/bullets, ≥3 lines outside known sections. Only then one Groq call labels each line by index (name, section_*, company, job_title, subheading, bullet, text); labels become `RawBlock.hint`s and the normalizer re-runs; the re-parse is kept only if it has fewer problems. Hallucinated/duplicate indices dropped; raw doc never modified. Wired via `TailorService.parse_resume()` / `normalize_raw()`; remaining issues exposed as `last_parse_issues` / `parse_issues` (for P3.5). The user's resume parses cleanly, so no LLM call is made for it. Live Groq check on an odd layout (unknown headings, plain company line): 1 call, ~1K tokens, fixed all problems. Also: date ranges accept "to", and only a month name may precede the year ("Engineer 2019 - 2023" keeps "Engineer") |
| P1.14 | **Rewrites must not lose information:** a prompt rule plus a validator check that flags a rewrite dropping key facts (tools, metrics, scope terms from the original) | `prompts/`, `validation/factual.py` | F48 | ✅ | Prompt: `rewrite_role.txt` lists what must be kept (tools, numbers, specific details). Validator: `FactualValidator.dropped_facts()` finds factual terms of the original missing from the rewrite and the share of content words kept (filler/generic verbs ignored, slashed terms compared per part) and short list items that vanish entirely ("pipeline stages, win rates, …"); a dropped term, < 50% retention or ≥ 2 lost list items turns PASS into NEEDS_CONFIRM with "the rewrite drops …" (REJECT stays REJECT). Lowercase single letters are never facts ("a" was matching "A/B"). On the real run it caught a rewrite dropping "Python-based" |
| P1.10 | Remove `validation_agent.py` + unused prompts (keep `final_review.txt` for the judge); sanitize resume text | `services/`, `llm/prompts/`, `validation/safety.py` | F32, F35 | ⬜ | |

## Phase 2: Novoresume-style template, ATS safety, auto page-fit

| ID | Action | Files | Resolves | Status | Notes |
|---|---|---|---|---|---|
| P2.1 | Template spec (see below) in DOCX + HTML, driven by `ResumePresentation` | `template_renderer.py`, `html_renderer.py`, `resume_document.py` | F25, F26 | ⬜ | |
| P2.2 | ATS template becomes the UI default; PRESERVE moves to "advanced" | `ui.py:143-148` | F28 | ⬜ | |
| P2.3 | Years of experience from date ranges (merges overlaps) → target 1 or 2 pages | new `analysis/experience.py` | F27 | 🟡 | Years part done in P1.5 (`years_of_experience()`, `years_phrase()`); page target still to do |
| P2.4 | Page-fit loop: render → PDF → count pages; trim in order Interests → low-relevance older bullets (keep ≥3 on the current role, ≥2 on others) → low-relevance projects → compact spacing; at most 4 renders; trims reported | new `rendering/page_fit.py`, `tailor.py` | F27 | ⬜ | |
| P2.5 | ATS round-trip QA: re-parse the output and check contact info, headings, roles, dates, bullets; fail loudly | `validation/output.py` | F29 | ⬜ | |
| P2.6 | Content checks: bullets per role, length, pronouns, buzzwords, tense, dates, % of bullets with metrics | new `validation/content_lint.py`, `ui.py` | F30 | ⬜ | |

**Template spec (P2.1):**
- **Page:** A4 with 0.7"/0.6" margins, single column. No tables, text boxes, icons or Word header/footer. Font: Arial.
- **Header:**
  - Name: 22pt bold, accent colour.
  - Headline: 12pt, accent colour.
  - Contact line: `email | phone | City, Country | linkedin | github`, followed by a thin rule.
- **Section headings:** 11.5pt bold uppercase with a rule underneath. Standard names only.
- **Section order:**
  - Default: Summary → Work Experience → Skills → Education → Projects → Certifications → Languages/Awards → Interests.
  - Under about 2 years of experience: Education moves before Experience.
- **Experience entries:**
  - Line 1: title in bold, dates right-aligned ("Jan 2022 – Present").
  - Line 2: Company · Location, in italic grey.
  - 3–6 bullets for recent roles, 2–3 for older ones.
- **Skills:** text only, at most 4 categories, JD-matched items first.
- **Output file name:** `First_Last_Resume_<Company>.pdf`.

## Phase 3: Suggest-and-confirm gaps + UX

| ID | Action | Files | Resolves | Status | Notes |
|---|---|---|---|---|---|
| P3.1 | Gap questions replace the "illustrative" suggestions ("JD requires X. Have you used it?"). A bullet is drafted only from the answer; the skill is added only if the user ticks it | `rewriter.py:88-133`, `tailor.py`, `ui.py:295-311` | F19 | ⬜ | |
| P3.2 | Profile store: confirmed answers become `user_confirmed` evidence, pre-filled on future JDs | new `services/profile_store.py`, `domain/evidence.py`, `.gitignore` | F19 | ⬜ | |
| P3.3 | "Add a job role" form → new Experience in date order, bullets polished from the input | `tailor.py`, `ui.py` | F20 | ⬜ | Design in PROJECT_OVERVIEW.md |
| P3.4 | Review UI: side-by-side diff + highlighted keywords, status badges, accept-all, match rate recomputed on edit, keyword gap table, score breakdown | `ui.py` | F17, F31 | ⬜ | |
| P3.5 | "Check parsed resume" step before tailoring (edit name, headline, links, roles, dates) | `ui.py` | F21, F22 | ✅ | "Tailor" now parses first (stage `check_parse`): parse problems shown as warnings, editable name / headline / email / phone / location / links and per job company, location, each role's title + start/end. `TailorService.apply_parse_corrections()` applies them to a copy (bullets untouched, evidence prefix follows a company rename, user revision recorded). The checked parse is passed to `generate_proposals(parsed=…)` and `tailor_resume(parsed=…)`, so the file isn't re-parsed (no second structure LLM call) and corrections survive; any correction switches PRESERVE output to the ATS template. Tested with Streamlit `AppTest` |
| P3.6 | `st.status` progress per stage; CLI parity | `ui.py`, `cli.py` | F31 | ⬜ | |

## Phase 4: Evaluation harness

| ID | Action | Files | Resolves | Status | Notes |
|---|---|---|---|---|---|
| P4.1 | Minimal harness + baseline (built during Phase 0): a few cases, deterministic metrics, `baseline.json` | `app/eval/`, `data/eval/` | — | ✅ | `python -m app.eval run [--live] [--tailor] [--case X] [--compare B] [--save B]`. Cases: `data/eval/cases.json` (replica PDF, sample DOCX, sample PDF) + gitignored `data/eval/private/cases.json` (real resume × FOX JD). Metrics: golden parse, parse stats, JD stats, score + match statuses, JD keyword coverage; with `--tailor`: proposals / changed / verdicts, suggestions, score after, pages; LLM calls / tokens / seconds / 429 retries. Offline mode uses no LLM (reproducible). Committed offline baseline `data/eval/baseline.json`; private live baseline `data/eval/private/baseline_stageA.json`. `--save` strips private cases from any file outside `data/eval/private/`. Golden projection moved to `app/eval/golden.py` |
| P4.2 | Full case set (10–12 anonymized pairs incl. new graduate, 12+ year senior, career changer, PDF, table DOCX, boilerplate JD) with `expected.json`. Metrics: attainable keyword coverage ≥95%, match rate before/after, zero fabrication, ATS round-trip 100%, page count, content checks, stuffing guard, cost per run | `data/eval/cases/`, `app/eval/` | — | ⬜ | |
| P4.3 | LLM-as-judge (different model family from the generator): 1–5 rubric plus pairwise original-vs-tailored, positions swapped; `python -m app.eval run --live\|--replay` → dated report | `app/eval/`, `prompts/final_review.txt` | — | ⬜ | Live runs cost money, so run only with the user's go-ahead |

---

## Findings index (from the 2026-09-30 audit)

| # | Finding | Impact |
|---|---|---|
| F1 | UI passes an Ollama model name to Groq; availability check ignores the model, so no warning | High |
| F2 | Root `ollama.py` stub shadows the real package | Med |
| F3 | LLM failures swallowed; rewrites silently return the original text | High |
| F4 | HTTP availability check before every LLM call | Med |
| F5 | No 429 / retry-after handling | High |
| F6 | JSON by prompt instruction, not a strict schema | Med |
| F7 | Planner + rewriter re-run on Apply despite pre-approved proposals | High |
| F8 | Strict Factual Mode applied after rendering (cosmetic) | Med |
| F9 | Keyword regex double-escaped → 0 keywords | High |
| F10 | `criticality` never set → perfect match scores 60/100 | High |
| F11 | No hard/soft skills, years, seniority or title; "and"-splitting creates junk requirements | High |
| F12 | Matching on whole sentences, not keywords (unlike ATS / Jobscan) | Med-High |
| F13 | Only matched bullets rewritten; all requirements sent to every bullet; no reorder or trim | High |
| F14 | One call per bullet with no role context; weak prompt; 5/6 prompts unused | Med-High |
| F15 | Validator rejects any new word (action verbs, adjectives) | High |
| F16 | Numeric regex misses 2M / 10x / 40K, so metric changes pass | High |
| F17 | The user's own edits are re-validated and silently dropped | High |
| F18 | Summary, skills and projects never tailored | High |
| F19 | Gap suggestions written as if the candidate already has the experience | Med |
| F20 | No "add job role" path | Med |
| F21 | LinkedIn / GitHub links never extracted, so they vanish from the output | High |
| F22 | Placeholder company/title rendered into the output | High (when triggered) |
| F23 | Synthetic "Previously:" note rendered as a bullet | Low-Med |
| F24 | DOCX tables processed out of reading order | Med |
| F25 | No headline field | Med |
| F26 | DOCX ignores `section_order`; HTML A4 vs DOCX Letter mismatch | Med |
| F27 | No page counting or auto-fit | High |
| F28 | UI defaults to PRESERVE, not the ATS template | Med |
| F29 | Output QA only checks non-empty + name; no ATS round-trip | Med |
| F30 | No content-quality checks | Med |
| F31 | No keyword gap table, diff view or score breakdown; Ollama-specific warnings | Med |
| F32 | Dead code (`validation_agent.py`, unused prompts) | Low |
| F33 | `changes.md` sections written twice; unreachable writes | Low |
| F34 | LLM usage not saved for `generate_proposals` | Low-Med |
| F35 | Resume text not sanitized before prompts | Low |
| F36 | PDF: candidate name taken from a project heading instead of the largest-font line | High |
| F37 | Model can't express several roles at one company or projects inside a role, so jobs are scrambled | High |
| F38 | PDF: `●` glyphs and zero-width spaces leak into bullets, education and the rendered output | High |
| F39 | PDF: wrapped bullet lines joined by the "starts lowercase" rule instead of indentation, so sentences split across bullets | High |
| F40 | PDF: non-bold section heading ("WORK EXPERIENCE") not detected | Med |
| F41 | PDF: right-aligned location/dates on the same line land in the wrong field (degree = "Bhubaneswar, India") | Med |
| F42 | Multi-category skill lines and labelled certification lines mis-split; certifications filed as interests | Med |
| F43 | Heading lines typeset in bold mid-paragraph confuse block typing | Low |
| F44 | JD: no title/company detected without explicit "Job Title:" / "Company:" labels | Med |
| F45 | JD: "Nice To Have, But Not Required" heading not recognised, so preferred items are marked required | High |
| F46 | JD: "and"-splitting creates junk requirements ("Design", "Mentor", "Develop") | High |
| F47 | JD keywords include heading and company words (WHAT, WILL, FOX, Corporation) | Med |
| F48 | A rewrite can drop information (Tableau bullet lost its KPI details) and still PASS | Med |

Research sources:
- Jobscan: [match rate](https://www.jobscan.co/blog/what-jobscan-match-rate-should-i-aim-for/), [ATS formats](https://www.jobscan.co/blog/20-ats-friendly-resume-templates/)
- Novoresume: [ATS checker](https://novoresume.com/tools/ats-resume-checker), [layouts](https://novoresume.com/career-blog/resume-layouts), [structure](https://novoresume.com/career-blog/resume-structure)
- Rezi: [Rezi Score](https://www.rezi.ai/rezi-docs/the-rezi-score-explained)
- Enhancv: [tailoring](https://enhancv.com/features/tailor-resume-to-job-description/)
- Teal: [JD match](https://www.tealhq.com/tool/resume-job-description-match)
- Groq: [rate limits](https://console.groq.com/docs/rate-limits)

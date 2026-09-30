# Action Items — Best Tailored Resume per JD

_Living tracker. Update an item's **Status** in the same commit that changes it; add a short note (commit subject or
what's left). Last updated: 2026-09-30._

**Goal:** every resume + JD run produces the best possible tailored resume: an accurate match score, strong
JD-aligned rewrites, a Novoresume-style ATS layout that fits the right length, and nothing fabricated.

**Status legend:** ⬜ Not started · 🟡 In progress · ✅ Done · ⛔ Blocked · ➖ Dropped

## Progress

| Phase | Items | ✅ | 🟡 | ⬜ |
|---|---|---|---|---|
| 0: Make the LLM path work | 10 | 1 | 0 | 9 |
| 1: Content quality | 10 | 0 | 0 | 10 |
| 2: Template, ATS, page-fit | 6 | 0 | 0 | 6 |
| 3: Gap questions + UX | 6 | 0 | 0 | 6 |
| 4: Evaluation harness | 3 | 0 | 0 | 3 |
| **Total** | **35** | **1** | **0** | **34** |

## Decisions (fixed by the user, 2026-09-30)

| Topic | Decision |
|---|---|
| Length | Auto by experience: 1 page under 8 years, 2 pages above. Trim the least JD-relevant bullets to fit |
| Page / dates | A4, "Jan 2022 – Present" (India / Asia / Europe standard) |
| Layout | Clean ATS single column following Novoresume's layout conventions (our own implementation, not their assets or text) |
| Gaps | Suggest-and-confirm: the tool asks, and drafts only from the user's answer. Never fabricate |
| Confirmed facts | Saved locally (`data/profile/facts.json`, gitignored) and reused across JDs |
| LLM | Claude API (`anthropic` SDK, `claude-opus-5-5`, structured outputs) as primary; Groq as free fallback. Claude Pro does **not** include API access, so this needs a pay-as-you-go API key (~$0.15–0.30 per resume) |

---

## Phase 0: Make the LLM path work, stop silent failures

**Exit gate:** a run on the real resume + a real JD shows rewrites that actually change; baseline metrics recorded (P4.1).

| ID | Action | Files | Resolves | Status | Notes |
|---|---|---|---|---|---|
| P0.1 | Add a Claude provider: `LLM_PROVIDER=anthropic`, `ANTHROPIC_MODEL=claude-opus-5-5`; `client.messages.parse()` / `output_config.format` against the `app/llm/schemas.py` models; explicit `effort`; handle `stop_reason` refusal / max_tokens; keep `usage_log`. Add the dependency, `.env.example` keys and a privacy note | `app/llm/client.py`, `pyproject.toml`, `.env.example`, `ARCHITECTURE.md` | F1, F5, F6 | ⬜ | Needs the user's API key for a live check |
| P0.2 | Provider-aware model picker: never pass an Ollama name to Groq/Claude; warning text per provider | `app/ui.py:137-142,201,285-293,387` | F1, F31 | ⬜ | |
| P0.3 | One cached health check per run that verifies the model exists; remove per-call `is_available()` | `client.py:95-120`, `rewriter.py:41,98`, `jd_analyzer.py:140`, `tailor.py:157` | F1, F4 | ⬜ | |
| P0.4 | Visible failures: rewrite status (ok / llm_error / rejected / unchanged) + error on `ChangeProposal`; UI banner; save usage in `generate_proposals` | `rewriter.py`, `change_proposal.py`, `tailor.py:122-159`, `ui.py` | F3, F34 | ⬜ | |
| P0.5 | Groq fallback robustness: 429 `retry-after` backoff, strict `json_schema` for gpt-oss | `client.py:_generate_groq`, `generate_json` | F5, F6 | ⬜ | |
| P0.6 | Move the `ollama.py` stub into `tests/conftest.py` so it stops shadowing the real package | `/ollama.py`, `tests/conftest.py` | F2 | ⬜ | |
| P0.7 | Skip planner + rewriter when proposals are pre-approved | `tailor.py:298-311` | F7 | ⬜ | |
| P0.8 | Strict mode decides before rendering; `changes.md` matches the rendered output; remove duplicate and dead writes | `tailor.py:391-539` | F8, F33 | ⬜ | |
| P0.9 | Quick fixes: keyword regex; `criticality` from priority + "perfect match = 100" test; numeric pattern covers 2M / 10x / 40K / $3.5M / 1,000+ / 5+ years | `jd_analyzer.py:47,239`, `scoring.py`, `factual.py:25` | F9, F10, F16 | ✅ | Score renormalised over non-empty buckets (perfect match = 100); keyword stopgap keeps only technical terms (C++, Node.js, AWS…); numbers include unit suffixes. +9 tests |
| P0.10 | `python -m app.cli check-llm`: one live structured call that prints provider, model, latency and tokens | `app/cli.py` | F1 | ⬜ | |

## Phase 1: Content quality

| ID | Action | Files | Resolves | Status | Notes |
|---|---|---|---|---|---|
| P1.1 | JD analysis v2: one structured call returns title, seniority, min years, hard skills, soft skills, must-have / nice-to-have, education, certs, each with a verbatim JD span (code drops anything not found in the JD). Frequency counted in code. No splitting on "and". Heuristic fallback stays | `jd_analyzer.py`, `domain/job.py`, `prompts/jd_analysis.txt` | F9, F11 | ⬜ | |
| P1.2 | Jobscan-style match rate as the headline score: keyword-level, weights hard skills > title > education/certs > soft skills, required ×1.5. Evidence strength becomes secondary. Target band 75–85% | `matcher.py`, `scoring.py`, `domain/report.py` | F10, F12 | ⬜ | |
| P1.3 | Planner v2: relevance score per bullet, reorder within each role, trim candidates; rewriter gets only the relevant requirements + allowed keywords | `tailor_planner.py`, `domain/tailoring.py` | F13 | ⬜ | |
| P1.4 | Rewrite v2, one call per role: strong verbs with no repeats, XYZ phrasing only with existing metrics, ≤28 words, JD spelling, no pronouns or buzzwords, never add numbers; returns `keywords_used` + `evidence_ids` | `rewriter.py`, `prompts/rewrite_role.txt`, `llm/schemas.py` | F14 | ⬜ | |
| P1.5 | Summary tailoring: years computed in code, real title, top evidenced JD skills, one real metric; validated | new `analysis/summary_writer.py`, `tailor.py`, `ui.py` | F18 | ⬜ | |
| P1.6 | Skills tailoring (deterministic): reorder by JD relevance, JD spelling via the alias map | new `analysis/skills_tailor.py` | F18 | ⬜ | |
| P1.7 | Rewrite project bullets through the same flow | `tailor_planner.py`, `rewriter.py`, `tailor.py` | F18 | ⬜ | |
| P1.8 | Validator v2: PASS / NEEDS_CONFIRM / REJECT; action-verb allowlist + alias-aware; reject new numbers and unevidenced tools or orgs; keep the user's own edits (logged as user-attested) | `factual.py`, `tailor.py:321-334`, `ui.py` | F15, F16, F17 | ⬜ | |
| P1.9 | Parsing fixes: LinkedIn/GitHub links (incl. DOCX hyperlinks), `headline` field, no placeholder rendering, handle "Previously:", DOCX walked in document order | `resume_normalizer.py`, `domain/resume.py`, `ingestion/docx.py`, `ingestion/pdf.py` | F21–F25 | ⬜ | |
| P1.10 | Remove `validation_agent.py` + unused prompts (keep `final_review.txt` for the judge); sanitize resume text | `services/`, `llm/prompts/`, `validation/safety.py` | F32, F35 | ⬜ | |

## Phase 2: Novoresume-style template, ATS safety, auto page-fit

| ID | Action | Files | Resolves | Status | Notes |
|---|---|---|---|---|---|
| P2.1 | Template spec (see below) in DOCX + HTML, driven by `ResumePresentation` | `template_renderer.py`, `html_renderer.py`, `resume_document.py` | F25, F26 | ⬜ | |
| P2.2 | ATS template becomes the UI default; PRESERVE moves to "advanced" | `ui.py:143-148` | F28 | ⬜ | |
| P2.3 | Years of experience from date ranges (merges overlaps) → target 1 or 2 pages | new `analysis/experience.py` | F27 | ⬜ | |
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
| P3.5 | "Check parsed resume" step before tailoring (edit name, headline, links, roles, dates) | `ui.py` | F21, F22 | ⬜ | |
| P3.6 | `st.status` progress per stage; CLI parity | `ui.py`, `cli.py` | F31 | ⬜ | |

## Phase 4: Evaluation harness

| ID | Action | Files | Resolves | Status | Notes |
|---|---|---|---|---|---|
| P4.1 | Minimal harness + baseline (built during Phase 0): a few cases, deterministic metrics, `baseline.json` | `app/eval/`, `data/eval/` | — | ⬜ | |
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

Research sources:
- Jobscan: [match rate](https://www.jobscan.co/blog/what-jobscan-match-rate-should-i-aim-for/), [ATS formats](https://www.jobscan.co/blog/20-ats-friendly-resume-templates/)
- Novoresume: [ATS checker](https://novoresume.com/tools/ats-resume-checker), [layouts](https://novoresume.com/career-blog/resume-layouts), [structure](https://novoresume.com/career-blog/resume-structure)
- Rezi: [Rezi Score](https://www.rezi.ai/rezi-docs/the-rezi-score-explained)
- Enhancv: [tailoring](https://enhancv.com/features/tailor-resume-to-job-description/)
- Teal: [JD match](https://www.tealhq.com/tool/resume-job-description-match)
- Groq: [rate limits](https://console.groq.com/docs/rate-limits)

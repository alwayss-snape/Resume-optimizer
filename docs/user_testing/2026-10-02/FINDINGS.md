# Cross-domain user testing: findings (2026-10-02, branch `fb_ksh`)

_Status: **planned (2026-10-02)** as Phase 8 in [ACTION_ITEMS.md](../../ACTION_ITEMS.md), items P8.1–P8.26 in stages
H–L. Each U finding maps to its item in the U findings index there. No code changed yet._

## How this was tested

A subagent took the role of job seekers from many fields, not only tech. It built 19 fictional personas and ran each
one through the tool.

- **Personas:** RN nurse; teacher moving into instructional design; electrician; warehouse/logistics; retail; sales
  account executive; accountant (CPA); lawyer; academic with a long CV; designer; executive (20+ years); new grad;
  career break / freelance; veteran; EU CV (English); German and Spanish CVs with JDs in those languages; India CV with
  a Chinese-script name; federal resume.
- **Edge files:** empty, corrupt, .txt, a .doc that is really a renamed .docx, encrypted PDF, scanned (image-only) PDF,
  a DOCX with text boxes, a keyword-stuffed resume, and a long resume for page-fit.
- **Date formats:** 12 variants, probed with `scripts/dates.py`.
- **JD variants:** HTML with emoji, a two-word JD, heavy boilerplate, German, Spanish, and JDs from a different field
  than the resume.
- **Offline path** (LLM forced unavailable): parse, analyze and render for every persona.
- **Full web API run with Groq** (parse → proposals → match preview → tailor → download): teacher, nurse,
  electrician, sales, Spanish. About 55–60K tokens in total.

**Inputs to reproduce:** the fictional resumes, JDs and scripts are in this folder.
- `scripts/make_personas.py` builds the resumes and JDs.
- `scripts/offline.py` runs parse, analyze and render with no LLM.
- `scripts/apiflow.py` drives the API end to end.
- `scripts/dates.py` is the date-format probe.

The scripts were written to run with `usertest/` as the working directory and `PROFILE_PATH` pointed at it, so that
`data/runs/` and the owner's profile stay untouched. Do the same when re-running them. `scanned.pdf` (3 MB) was left
out; recreate it as any image-only PDF. Run outputs were not kept.

**Not tested:** PRESERVE ("keep my layout") mode, the add-content and add-job flows with the LLM, strict mode, the
React UI in a browser (source copy only), real concurrency and session expiry, uploads over 5 MB, and PDF output
without LibreOffice. LibreOffice is installed at `/Applications/LibreOffice.app` but not on PATH; `pdf_converter.py`
finds it, so PDF output and page-fit did run.

**Root cause behind many of these:** all 8 anonymized eval cases are tech roles (data, backend, SRE, ML, frontend,
PM), so none of the problems below could appear in the eval. Add non-tech, non-US and non-English eval cases built
from these personas.

## Top 10 by user impact

1. **U1 (Critical): Content is silently deleted, yet the run reports success.**
   - A section heading the parser doesn't know falls into the previous section or is dropped.
   - The ATS round-trip check compares against the already-damaged parse, so it never notices.
   - Teacher: "Professional Journey" without the LLM leaves only name and education.
   - German and Spanish CVs: the output is the name, a heading and the email, with `success: true`.
   - Lawyer: the bar admissions line is dropped.
   - "Volunteer" and "Languages" are folded into Skills. Text inside Word text boxes vanishes.
2. **U2 (Critical): Facts end up under the wrong job, which breaks "never invents facts".**
   - Lawyer: a job line of 100+ characters is read as a bullet, so the clerkship merged into the Associate job.
     Automatic reordering then put the clerkship bullet under the law firm.
   - EU CV: the internship was given the first job's dates. India CV: the second job shows two date lines.
   - Nurse (LLM run): a 120-hour ICU student rotation became "Administered direct ICU patient care at Mayo Clinic
     Hospital" under the Med-Surg job, and it passed the fact check.
3. **U3 (Critical): Phone numbers disappear.**
   - "(602) 555-0147" and most international numbers (+33, +49, +34, +91 groupings) are not matched.
   - Cause: `PHONE_RE` in `app/analysis/resume_normalizer.py` (around line 27).
4. **U4 (Critical): Common job-line formats outside tech are misread.**
   - "Title, Company, City, dates" leaves the company empty.
   - "Title\tEmployer" with dates on the next line makes the title the company and puts "03/" in the title.
   - Title and company are swapped when the role word is not in `_ROLE_WORDS_RE` ("Delivery Driver",
     "Production Supervisor", "SVP, Global Supply Chain").
   - The LLM structure step labels whole lines, so it cannot split one line into title and company.
5. **U5 (High): Many date formats are lost, which zeroes out years of experience.**
   - Lost: "Summer 2019 – Fall 2020", "03/2019 – 06/2021", "01/09/2019 – 31/08/2023", "to date", "Till Date",
     "Ongoing", "2019-03", "Jan '19", a lone year such as "2018".
   - "07/2022 – Present" keeps only the year. A future start date is accepted without a warning.
   - Knock-on: the page target, the summary's years and the content checks all go wrong.
6. **U6 (High): Rewrites and summaries borrow JD wording and overclaim; the fact check passes them.** Broader than
   P1.15. Seen in 4 of 4 English LLM runs.
   - Teacher: "applying adult learning theory and instructional design models" (not in the resume);
     "Builds and delivers interactive e-learning modules using Rise 360" (the resume says "self-taught").
   - Electrician: "Enhanced safety standards through NEC compliance" (invented).
   - Sales: "Senior Account Executive with 10+ years B2B SaaS sales in B2B SaaS. Builds and delivers enterprise
     revenue growth using B2B SaaS."
   - Nurse: "03/ with 5+ years … Builds and delivers patient care using Epic, RN, ICU and BLS."
7. **U7 (High): The score is unfair to non-tech candidates and easy to game.**
   - Multi-word keywords must match in full: "Salesforce CRM" is missing although "Salesforce" is present.
   - Slash terms are not split: "Compact/NLC", "English/Spanish".
   - "OSHA 10 or 30" never matches "OSHA 30". A Master's doesn't satisfy "Bachelor's degree".
   - Acronyms are not linked to their expansions (GAAP, LOTO).
   - A barista with one Skills line pasted from the JD scored 87.5%, versus 37.5% for a strong account executive on
     the same offline path.
8. **U8 (High): Non-English and non-ASCII text breaks end to end.**
   - Tokenizers are ASCII-only (`keyword_match.py` around line 31, `jd_analyzer.py` around line 79): "Enfermería"
     becomes "Enfermer", and the user is asked "Have you worked with Enfermer?" in English.
   - A Chinese-script name renders blank in the PDF, because Arial has no glyphs for it.
   - File names lose non-ASCII letters, e.g. "Luc_a_Fern_ndez_Garc_a" (`rendering/layout.py` around line 110).
9. **U9 (High): Academic, legal, federal, licence, military and EU CV conventions are not modelled.**
   - The `Resume` model has no publications, grants, bar admissions, licences (separate from certifications),
     languages, volunteer work, teaching, service, clearance or references.
   - "Academic Appointments" matches "academic", so every appointment becomes an Education entry.
   - A 45-publication CV was trimmed toward one page, lost "Research Interests", and still ended at 3 pages.
   - Licence lines split on commas into fake certifications ("New York", "2021", "exp. 03/2026").
10. **U10 (High): Failure states mislead, and cloud processing is not disclosed.**
    - A corrupt or encrypted file gives HTTP 500 and "Something went wrong on our side. Please try again."
    - A scanned PDF parses as empty with only "no candidate name".
    - Groq 429 back-offs of 10–19 s each are invisible; drafting took 60–74 s instead of 28 s.
    - "Just check my match" silently falls back to the heuristic, which scores "Dental", "Vision", "ADA", "PTO" as
      skills and gives a two-word JD 100%.
    - Nothing in the UI says resume text is sent to Groq. The README still says "local-first".

## All findings by area

"Confirmed" means reproduced; "Suspected" means code-read only. Line numbers are approximate as of `30cf2c2`.

### Ingestion

- **U1. Unknown section headings swallow or drop content.** Critical. Confirmed.
  - `SECTION_KEYWORDS` (`resume_normalizer.py` around line 72) lacks: journey, licences/licenses alone,
    publications, volunteer, languages, references, training, rotations, bar admissions, grants, teaching, service,
    memberships, military, clearance, personal details, declaration, and all non-English headings (Berufserfahrung,
    Experiencia, Formación…).
  - Unknown sections go to the catch-all (around line 679): kept as evidence, never in `Resume` or the output.
  - Recommendation: an "Other / custom sections" model kept verbatim under its original heading; a wider and
    multilingual heading vocabulary; a coverage check (share of source lines that reach the output) that blocks
    "success" and warns loudly; show these sections on Check details.
- **U11. Text boxes are ignored.** High. Confirmed (`resumes/textbox.docx`).
  - An "Office Manager" job inside a text box vanished with no parse issue. Canva and many Word templates use them.
  - Recommendation: read `w:txbxContent`, or at least warn when text boxes exist.
- **U12. Name and links taken wrongly in header/table layouts.** High. Confirmed (`resumes/designer.docx`).
  - The name became "Figma" and the file `Figma_Resume_Company.docx`. The real name was in the page header with
    " · " separators and the `len < 40` rule skipped it.
  - `URL_RE` (around line 29) only knows some top-level domains: `lenapark.design` and `priyaraman.design` were
    dropped, for JDs that require a portfolio.
  - Recommendation: accept any top-level domain; take the name from the first segment of a separated header line.
- **U13. A job line of 100+ characters becomes a bullet.** High. Confirmed (lawyer).
  - `_is_dated_line` (around line 216). Long legal and federal titles are common.
  - Recommendation: decide by the date-range pattern, not by length.
- **U14. Other upload types and broken files.** Medium. Confirmed.
  - .doc, .txt, .rtf, .odt are refused. Corrupt .docx and encrypted PDF give an unhandled 500
    (`PackageNotFoundError` / "document closed or encrypted"). Scanned PDF parses empty; `ocr.py` is a stub.
  - Recommendation: specific messages ("This PDF is password-protected", "This looks like a scanned image"); accept
    .txt and paste-as-text; consider converting .doc/.odt/.rtf with LibreOffice.
- **U15. PDF bullets with a "·" glyph are not recognised.** Low. Suspected (generated PDFs may exaggerate it).
  Bullets became companies.

### Dates and structure

- **U4. Job-line formats.** Critical. Confirmed. See the top 10.
  - Recommendation: split "Title, Company, City, dates" on commas using role words and the date position; give the
    LLM a verbatim "split this line into fields" task; grow `_ROLE_WORDS_RE` (around line 112) with nurse,
    electrician, driver, supervisor, clerk, attorney, paralegal, barista, professor, postdoc, NCOIC and others.
- **U5. Date formats.** High. Confirmed (`scripts/dates.py`).
  - Recommendation: support seasons, MM/YYYY, DD/MM/YYYY, ISO, 'YY, "to date"/"till date"/"ongoing"/"heute"/
    "actualidad", lone years; flag future dates.
- **U16. Later jobs inherit the previous job's location or dates.** Critical. Confirmed (EU, India).
  - The "new title after bullets → another role at the same company" path (around line 476) copies company and
    location.
  - Recommendation: never copy a right-hand column that is a date; inherit only when the company is truly missing;
    show the inheritance on Check details.
- **U17. Rotations, training, board roles, publications, references become fake jobs or education.** High.
  Confirmed. Content checks then nag "0 bullets; aim for 2–4" about them.
- **U18. Two degrees on two lines merge into one entry.** Medium. Confirmed (executive, lawyer, teacher). Printed
  oldest-first; round-trip warns "education entry not read back".
- **U19. Concurrent jobs and career breaks.** Medium. Confirmed. "Career Break — Family Caregiver" parsed
  acceptably; "Delivery Driver (part-time, concurrent) — DoorDash" swapped. No concept of concurrent roles or gaps,
  no guidance on presenting a break.
- **U20. Check details can't show or fix the problems above.** High. Confirmed by reading `Details.tsx`.
  - Only candidate fields and jobs are shown. Education, skills, certifications/licences and other sections are
    invisible.
  - Parse-issue copy is developer language ("bullets found but no experience or projects", "experience without a
    company (exp_001)").
  - Recommendation: show every section and a plain "We couldn't place these lines" list the user can assign.

### JD analysis

- **U21. The heuristic fallback is tech-biased and boilerplate-blind.** High. Confirmed offline.
  - Keeps only capitalised words, acronyms and symbol tokens: lowercase trade terms (forklift, wiring) are lost;
    multi-word terms split ("Generally", "Accepted", "Principles"; "Six", "Sigma"; "Chain").
  - Benefits and EEO text become keywords. A two-word JD gives 100%.
  - This is what every user gets once the Groq daily limit is used up.
  - Recommendation: strip boilerplate blocks, keep multi-word noun phrases, label fallback scores "approximate".
- **U22. The LLM path handles boilerplate, but not HTML or emoji.** Medium. Confirmed via `/api/analyze`. The
  boilerplate JD scored a sensible 73.7. The HTML JD produced keyword "h2" and title "🚀 Senior Accountant 💼"; "PTO"
  stayed a hard skill. Recommendation: strip tags, entities and emoji; block-list benefits terms.
- **U23. Non-keyword requirements are invisible.** Medium. Confirmed (nurse, electrician, retail, federal). State
  licences, clearances, shift availability, lifting, driver's licence, languages, years, GS-level specialized
  experience. Recommendation: a "Requirements checklist" the user ticks once, shown separately from keyword match.
- **U24. Company often not detected, so files are named `…_Resume_Company.docx`.** Medium. Confirmed, including the
  LLM path. Recommendation: omit the suffix when unknown (`output_basename`, default `company="Company"`).

### Scoring

- **U7. Unfair and gameable.** High. Confirmed. See the top 10.
  - Skills-list matches count the same as experience matches (`resume_sections`); no frequency or context weighting.
  - Recommendation: split slashes; turn "X or Y" into alternatives; ask the LLM for short atomic keywords; partial
    credit for the head of a multi-word term; weight skills-only matches lower; flag skills with no supporting bullet.
- **U25. A low score isn't explained.** Medium. Confirmed. Nurse vs sales JD scores 0; the teacher scored 16% and is
  shown the same "aim for 75–85" target. Recommendation: a field-mismatch message and career-changer guidance.
- **U26. Modes disagree for the same pair.** Low. Confirmed. Nurse 61.7 offline vs 45.7 with LLM; sales 37.5 vs
  19.7. Location words ("Arizona", "DC") count as hard skills.

### Rewrites and honesty

- **U6. JD borrowing and overclaims pass the fact check.** High. Confirmed. Recommendation: treat JD-only content
  words as unsupported, not just numbers and tools; check claim phrases like "demonstrating X experience" /
  "applying X"; have the summary validator reject non-skills (RN, ICU) and repeated phrases.
- **U27. The summary prompt is tech-shaped.** High. Confirmed.
  - `prompts/summary.txt` line 7 asks for "Builds and deploys … using X, Y, Z".
  - It replaced good original summaries (nurse, sales) and used parse garbage ("03/") as the title.
  - Years conflict with the resume (sales 7 vs 10+; nurse 6 vs 5+); this is open issue 3 and it is common.
  - Recommendation: domain-neutral templates; keep the user's summary unless asked; never print a title that fails a
    sanity check.
- **U28. Domain voice is flattened.** Medium. Confirmed. "Precept new graduate nurses" → "Educated 8 new graduate
  nurses"; "Closed largest deal in company history" → "Closed largest company deal"; "Built pipeline" → "Managed
  pipeline".
- **U29. The validator is inconsistent about verbs.** Medium. Confirmed. It rejected "Managed" and "team" but passed
  "Exceeded", "Generated", "Delivered", "Interpreted", "Administered" and "Enhanced safety standards".
- **U30. Automatic bullet reordering is not approved by the user.** Medium. Confirmed. "Reordered bullets by JD
  relevance" runs even with 0 accepted proposals; with U13/U16 it moves bullets into the wrong job.
  Recommendation: make reordering a visible, revertible proposal.

### Gap questions and add flows

- **U31. Gap question wording is template-driven and often absurd.** Medium. Confirmed. "Have you worked with
  Collaborate?", "…with Bachelor's degree preferred?", "…with GED or High school diploma or GED?", "…with OSHA 10 or
  30?", "…with SMEs?", "…with Enfermer?". It also asks about things already present (Salesforce, NLC, Spanish).
  Recommendation: templates by kind (licence/certification: "Do you hold…?"; education: "Do you have…?"; soft
  skill: "Can you give an example of…?"); suppress partial matches; ask in the JD's language.
- **U32. Ticking a keyword with no answer adds it to Skills and doubles the score.** Medium. Confirmed: teacher ticked
  ADDIE and SAM, 16.2 → 32.4. The "ATD Instructional Design Certificate, 2024" also landed in Skills, not
  Certifications. Recommendation: ask "where did you use it?" and remind that interviewers will ask.
- Add-content and add-job flows were not tested end to end.

### Output and rendering

- **U8. Chinese-script name blank in PDF; file names lose non-ASCII letters.** High. Confirmed. Recommendation: embed
  a fallback font covering CJK, Cyrillic and other scripts; keep Unicode or transliterate in file names.
- **U9. ATS template and page targets don't suit academia, law, federal or creative.** High. Confirmed.
  - Page target comes from years: an academic CV with lost dates gets target 1 and ends "Still 3 pages after
    trimming".
  - Federal resumes need hours, salary, supervisor and GS grade per job; these became reordered bullets.
  - Recommendation: CV and federal modes (no page cap, structured fields); a "don't trim" option; a user-selectable
    page target.
- **U33. Page-fit trimming messages are unhelpful.** Medium. Confirmed (`longnurse`). Many identical truncated lines,
  no job named, no way to restore or choose before the file is made.
- **U34. "Ready, with warnings" is mostly noise.** Medium. Confirmed. The round-trip reports our own template quirks
  ("1 job entries read, 2 rendered", undated roles, two-degree education). Most persona runs ended `success=false`
  while the truly destructive runs (Spanish, German) ended `success=true`.
- **U35. HTML output can't be downloaded through the API.** Low. Confirmed. `FILE_KINDS` in `app/api/routes.py` has
  only docx, pdf and changes.

### UX and copy

- **U36. No privacy notice about cloud processing.** High. Confirmed: nothing in `web/src` mentions Groq, cloud or
  where data goes. Recommendation: a notice on upload ("Your resume text is sent to Groq to draft rewrites; files are
  deleted when your session ends").
- **U37. Error and degraded states.** High. Confirmed. See U10 and U14. `/api/analyze` returns no LLM status, so the
  UI can't say a score is approximate.
- **U38. The flow assumes a tech resume.** Medium. Placeholders like "e.g. Senior Data Scientist"; content checks push
  "add numbers" for trades and care work; "keyword match rate" is unexplained. Recommendation: domain-neutral examples
  and a softer metrics nudge for non-quantified roles.

### Robustness and errors

- **U39. Rate limiting is invisible.** Medium. Confirmed: 18 "Groq rate limited (429); retrying in up to 19 s" log
  lines over 5 runs while SSE progress stalled. Recommendation: a progress event while backing off; a clear "daily AI
  limit reached; drafting unavailable until X" state.
- Session expiry, busy session and the 5 MB upload limit look reasonable from code. Low, suspected. The rate limit
  (30 steps per hour per IP) is shared by everyone behind one NAT.

### Missing features users expect

- Cover letter.
- Re-use across multiple JDs, and a history (only gap answers persist today).
- Paste-text resume input, LinkedIn import, .doc/.odt support.
- Non-English UI and region presets: US Letter vs A4 (A4 is hard-coded); US resume vs EU CV (photo, date of birth);
  Indian format (personal details, declaration), with advice to drop them for US/UK jobs.
- Requirements checklist (U23), career-gap guidance, concurrent roles.
- A "keep my sections exactly" safety mode.
- Accessible output: tagged PDF not verified.

## Verdict by persona

| Persona | Value today | What breaks |
|---|---|---|
| RN nurse | Low, risky | Phone dropped; licences split into junk certs; rotations become jobs; garbled summary; ICU rotation overclaimed; false gaps for NLC and Spanish |
| Teacher → instructional designer | Low | Offline loses all experience; LLM injects "adult learning theory" and "e-learning"; portfolio link and contract dates lost; 16% with no career-changer guidance |
| Electrician | Low | Licences filed as bullets; company empty; invented "Enhanced safety standards"; OSHA 30 vs "OSHA 10 or 30" missed |
| Warehouse / logistics | Low–medium | Concurrent gig job swapped; heuristic score 11% |
| Retail / hospitality | Medium | Phone dropped; company empty; otherwise readable |
| Sales AE | Low–medium | 19.7% despite a strong fit; garbled summary with inflated years; useful rewrites dropped |
| Accountant (CPA) | Medium | MM/YYYY dates lost; certification split into "New York" and "2021"; degree-level miss |
| Lawyer | Harmful | Bar admissions dropped; clerkship merged into the firm job; publications become a fake job |
| Academic (long CV) | Harmful | Appointments and publications become Education; forced toward 1 page; Research Interests removed |
| Designer | Low | Name = "Figma"; portfolio link dropped |
| Executive (20+ years) | Medium | Some title/company swaps; second degree lost |
| New grad | Medium–good | Phone dropped; coursework parsed as the degree; projects work |
| Career break / freelance | Medium | Parses acceptably; no gap guidance |
| Veteran | Medium | Military jargon not translated; "Supply Chain" → "Chain"; 9.5% |
| EU CV (English) | Harmful | DD/MM dates lost; internship given wrong dates; phone dropped; languages and hobbies become Education |
| German / Spanish | Unusable | Everything deleted, reported as success; keywords truncated at accented letters |
| India / CJK name | Low | Name blank in PDF; "Till Date" lost; duplicated dates; personal details and declaration printed as Education |
| Federal | Low | No title or dates; hours, salary, supervisor become reordered bullets; GS terms not understood |

## What worked well

- LLM JD analysis handles boilerplate, keeps requirement lines verbatim, and splits preferred from required.
- When the deterministic parse fails on an English resume, LLM structure extraction often recovers it.
- The fact check does catch some unsupported additions ("team", "interdisciplinary").
- The keyword table and `changes.md` are transparent; page-fit reports what it removed.
- Upload type and magic-byte checks work, with clear messages for wrong types.
- SSE progress, session cookies and downloads worked end to end, with no crashes on valid files.
- Numbers were preserved in every observed rewrite.
- Standard US single-column "Title | Company | dates" resumes render cleanly; DOCX/PDF generation was reliable.

## Suggested starting point for planning

Start with U1, U3, U13 and U16, because they cause silent data loss or misattribution. A content coverage check that
blocks "success" when source lines are lost would catch most of these early. Add non-tech, non-US and non-English
eval cases from this folder's personas so regressions show up in `pytest -m eval`.

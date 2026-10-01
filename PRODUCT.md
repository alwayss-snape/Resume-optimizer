# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Job seekers in any field, from new graduates to senior people, applying to a specific job and wanting their resume
tuned to that job description without misrepresenting themselves. They arrive with an existing resume (DOCX or PDF)
and a pasted job description, usually mid-application and under some time pressure, often repeating the flow for
several jobs.

## Product Purpose

Tailor scores how well a resume matches a job description, drafts rewrites of the resume's bullets, summary and skills
that lean toward the job, lets the user review each change, and produces ATS-ready DOCX and PDF files with a log of
every change. Success: the user leaves with a stronger, truthful resume for this job, and trusts every line in it.

## Positioning

- **Never invents facts.** Every rewrite is traced to evidence already on the user's resume; new numbers or terms are
  rejected by deterministic checks, not by the model's good intentions.
- **Honest match score.** A keyword match rate before and after, with what was found and missing; it does not push the
  user to stuff keywords.
- **ATS-safe files.** Generated DOCX and PDF are read back to prove an applicant tracking system can parse them.

## Operating Context

Flow: Upload (resume + job description) → Check details (correct what was read) → Review (accept, reject or edit each
rewrite; answer gap questions; add content in the user's own words; live match score) → Results (before → after score,
downloads, page preview, change log, content checks). A shorter path, "Just check my match", shows only the match
report. Drafting takes tens of seconds and streams progress. Users compare rewrites against their original wording
closely, so long reading and side-by-side text comparison are central.

## Capabilities and Constraints

- React SPA (`web/`: Vite, TypeScript, Tailwind 4, motion, zustand) on a FastAPI backend (`app/api/`); CLI also exists.
- The LLM edits content; deterministic code owns structure, formatting, validation and file generation.
- A resume never goes to browser storage; run state lives in memory and the server session.
- Output templates: ATS default (A4) or "keep my layout" (DOCX only).
- Undecided: public hosting (P5.7 is shelved pending a broader discussion), and how LLM cost is handled if it is public.

## Brand Commitments

- Name: **Tailor**, with the descriptor "Resume Studio".
- Voice: plain, calm, specific wording; no hype; state limits honestly (for example "Nothing is invented").
- Visual world (chosen by the owner 2026-10-01, replacing the dark "Succession" look): **Editor's Proof**, changes
  shown the way an editor marks a proof. Bright by default with a matching dark mode that follows the system. The
  direction contract lives in `.impeccable/surfaces/web-src-pages-landing-tsx.md`; `DESIGN.md` is written when the
  build is finished.

## Evidence on Hand

- An anonymized evaluation set of 11 resume + job description cases (`data/eval/`) and their measured results.
- No testimonials, user counts, customer logos, press or benchmarks against other tools exist; do not fabricate them.

## Product Principles

1. Truth over polish: never show or imply a claim the user's resume cannot support.
2. The user decides: every change is visible, reversible and attributed before any file is made.
3. Show the evidence: scores, matches and checks are explained, not just displayed.
4. Calm under pressure: a job application is stressful; the interface stays clear, quiet and fast to scan.

## Accessibility & Inclusion

WCAG 2.2 AA: text contrast, 3:1 for UI boundaries, full keyboard use with visible focus, 44 px touch targets,
reduced motion respected, screen-reader announcements for progress and score changes. Works on phones (390 px) and
desktops (1440 px).

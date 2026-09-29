# Resume-optimizer — Status

_Branch: `fb_ksh`. Last updated: 2026-09-29._

This file is a handoff note for whoever (or whichever Claude session) picks this
project back up next — including Claude Code running in VS Code. Read this
before making changes so you don't re-discover context that's already settled.

## Context

User ran the real tool against their own resume/JD and found it badly broken.
Fix order, explicitly approved by the user ("everything in this order"):

1. Data-integrity bugs in parsing/normalization
2. JD requirement extraction quality (was matching against boilerplate)
3. Visual/formatting polish of the DOCX and HTML output
4. New "add job role" UI feature

## Done (committed on `fb_ksh`, not yet pushed to `origin/fb_ksh`)

- `336a106` — **Fix resume parsing data-integrity bugs found against real resume**
  Fixed in `app/analysis/resume_normalizer.py`: trailing "|" left in job titles,
  skills getting shredded by embedded parentheses (new paren-depth-aware
  splitter), interests misclassified as certifications (now keyed off section
  heading, not line-text heuristics), missing `achievements` field never wired
  into the `Resume` object, missing candidate location extraction from the
  header line. Bullet-glyph and `location` field fixes in `app/ingestion/docx.py`
  / `app/domain/resume.py` were already in place. Verified against the user's
  actual resume file, not just synthetic fixtures.

- `3b81757` — **Use LLM to identify genuine JD requirements instead of naive
  line-splitting**
  Full rewrite of `app/analysis/jd_analyzer.py`. Adds `_reflow_lines()` to
  rejoin hard-wrapped JD text before scoring, and `_llm_select_requirement_lines()`
  which sends the LLM a numbered candidate list and asks it to return only the
  INDICES of genuine requirement lines (never freeform text) — preserves the
  pre-existing verbatim-from-JD auditability guarantee. Falls back to the
  original deterministic heuristic whenever the LLM is unavailable, errors, or
  returns a degenerate/empty selection over a non-trivial candidate pool.
  Hallucinated out-of-range indices are filtered out. New schema
  `JDRequirementSelection` in `app/llm/schemas.py`. 7 new tests in
  `tests/unit/test_jd_analyzer_llm.py` using a fake LLM client (real Groq
  end-to-end testing is blocked by this sandbox's network egress policy, not
  a code issue).

- `1925946` — **Polish resume output formatting (DOCX/PDF + HTML preview)**
  Full rewrite of `app/rendering/template_renderer.py` (the renderer that
  actually produces the downloadable PDF, via LibreOffice conversion of its
  DOCX output — NOT `html_renderer.py`, which only powers the separate
  in-browser preview) and `app/rendering/html_renderer.py`, sharing one visual
  language: accent-colored uppercase section headers with a rule divider,
  title+dates on the same line (right tab stop in DOCX / flexbox in HTML),
  italic gray "Company · Location" meta line. Verified visually — LibreOffice-
  rendered PDF and a real-Chromium (Playwright) screenshot of the HTML — not
  just by tests. 3 new tests in `tests/unit/test_template_renderer_standalone.py`.

**Push status:** these 3 commits are ahead of `origin/fb_ksh`. Not yet pushed —
see push setup below.

## Not started: item 4 — "add job role" form

Investigated, not yet coded. The gap: `TailorService.incorporate_user_addition()`
in `app/services/tailor.py` (~line 161-227) can only append one polished bullet
to an *existing* `Experience`, or create a new `Project` — there's no path to
create a brand-new `Experience` entry.

Planned design (not yet reviewed in detail with the user beyond "yes, build it"):

- **Backend** (`app/services/tailor.py`): new method, e.g.
  `add_new_role(self, resume, evidence_list, job_desc, role_data: dict,
  description_text: str = "")` that builds a new `Experience` (needs
  `Experience` added to the `from app.domain.resume import Project, Resume,
  ResumeBullet` import — not currently imported), splits the pasted
  project/description text into multiple chunks, and polishes each into its
  own grounded bullet (unlike the single-bullet flow in
  `incorporate_user_addition`). Wire into `tailor_resume()` next to the
  existing `addition_text`/`addition_target` handling (~line 377-383); likely
  needs a new `new_role_data: Optional[dict]` param, and should force
  `mode = "ATS_DEFAULT"` when present, same as the existing addition_text
  logic does.
- **Frontend** (`app/ui.py`): add "➕ Add as a new Job Role" to `target_labels`.
  The target-choice selectbox currently lives *inside*
  `st.form("proposal_review_form")` — it must move **outside** the form, since
  Streamlit forms don't rerun until submitted, and dynamic field reveal needs
  an immediate rerun on selection. New structured fields once "new role" is
  selected: Company Name (not explicitly requested by the user, but
  structurally necessary — flag before assuming), Designation/Job Title,
  Location, a "currently working here" checkbox, Start/End Date (leaning
  `st.date_input`, formatted like "%b %Y"; End Date disabled/shown as
  "Present" when the current-job checkbox is checked), and a text area for
  the role's project/description paste. Wire the collected data through to
  the new backend method on "Apply & Generate".

## Known, not-yet-actioned (don't fix unprompted)

- Dead code in `app/services/tailor.py`'s `tailor_resume()`: a duplicate block
  inside an `except Exception: pass` handler writes to an already-closed file
  handle if ever reached. User has not asked for this to be fixed.
- The user's real resume source `.docx` has "LinkedIn | Email | Leetcode" as
  placeholder text with no real hyperlinks behind it. User said they'd fix
  this themselves in the source file — no action needed here.

## Push setup

`origin` → `github.com/alwayss-snape/Resume-optimizer.git`. This environment's
sandboxed shell has no GitHub credentials of its own (separate from the user's
real machine), so a deploy key was generated for push access, scoped to this
repo only. Once the corresponding public key is added on GitHub
(Settings → Deploy keys, with write access), push with:

```
git push origin fb_ksh
```

(git is configured locally in this repo — `core.sshCommand` and the `origin`
remote URL — to route through the deploy key automatically.)

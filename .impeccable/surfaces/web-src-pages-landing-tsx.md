---
version: 1
slug: "web-src-pages-landing-tsx"
primary_target: "web/src/pages/Landing.tsx"
related_targets: ["web/src/pages/Review.tsx","web/src/pages/Results.tsx","web/src/pages/Details.tsx","web/src/pages/Report.tsx"]
---

# Surface brief: Tailor web app (landing first; the world carries to every screen)

## Scope and mode
Landing (`web/src/pages/Landing.tsx`): Persuade. Details, Report, Review, Results, progress: Operate, same world.
Audience: job seekers in any field, mid-application, a little anxious. Task: upload a resume + job ad, review every
change, download truthful ATS files. Proof on hand: the product's own mechanism only; no testimonials or numbers.
Owner constraints: bright by default, theme follows the system (light and dark both designed), WCAG 2.2 AA; a 3D resume
on the landing hero that tilts with the cursor and visibly rewrites; a living fluid background; depth on work screens.

## Direction contract
THESIS: Every change is shown the way an editor marks a proof: struck, inserted, explained in the margin, and the
user's to keep or reverse. Refuses the SaaS "AI resume builder" (gradients, sparkles, gauges) and the dark luxury look.
OWN-WORLD: Bright bond paper (#FFFFFF sheets on a #F6F6F3 desk), graphite ink #1B1B1F, editor's blue pencil #2F62D8
as the single action colour (buttons, focus, insertions, carets), proof red #BF3328 only for removed words and
strike marks, highlighter yellow #F2D43D swiped behind matched job keywords. Sheets have real paper edges, a soft
contact shadow and a slight lift; no rounded SaaS cards, no gradients, no glass. Type: Schibsted Grotesk for UI and
headings (a newsroom face), Source Serif 4 for resume/proof text so documents read as documents; margin notes in
Source Serif italic. Marks are drawn SVG strokes (caret, strike, loop, margin rule), never icon tiles. Dark mode: the
same proof under a desk lamp at night: graphite desk #16171B, sheets #1F2026, ink #ECECEF, pencil #8FAEFF, red #FF8A7E.
STORY: the visitor sees their kind of document being edited honestly, understands that nothing new is invented and
every mark can be undone, uploads, reviews each marked change, and leaves with files they trust.
FIRST VIEWPORT: left 5 columns: kicker "Resume tailoring", headline, one line on "nothing is invented", primary
"Tailor my resume" (blue) and secondary "Just check my match". Right 7 columns: a 3D proof sheet of a fictional
resume (labelled "Example") on the desk, tilting toward the cursor; marks draw themselves in a loop: a filler word is
struck in red, a caret inserts a job keyword in blue, a yellow swipe lands on matched keywords, a margin note gives
the reason, a small reading at the sheet's foot shows matched job keywords ticking on, labelled "Example" in every state (animated, still frame, fallback, screen reader); no percentage is shown. Behind everything: blue ink slowly
diffusing in water (fluid shader), pulled softly toward the cursor, at low contrast (tint at most ~6% behind text in light; the text column masked) so text stays AA. The upload form
starts directly below the fold.
FORM: Editor's Proof: the copy editor's proof sheet as a working interface; position 1 of 7 on the grounded list
(Impeccable's pick, chosen by the owner); seed key 7171ff9a. Raises carried: depth as planes moving at different
speeds (desk, sheets, marks); one light source (the tailored resume is the brightest sheet); evidence strength as line
weight; scale follows importance.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Implementation decisions (P6.2 review, 2026-10-01)
3D: the proof sheet is real DOM text + SVG marks in a CSS 3D-transformed plane (perspective, cursor tilt with spring
damping, layered depth for desk / sheet / marks); the fluid field is one raw WebGL fragment shader (~3 KB). No three.js,
so text stays crisp, selectable and translatable. Still frame under reduced motion; static sheet with no WebGL.

Tokens (both themes; every text pair ≥ 4.5:1, boundaries ≥ 3:1):
| role | light | dark |
|---|---|---|
| desk (bg) | #F6F6F3 | #16171B |
| sheet (panel) | #FFFFFF | #1F2026 |
| sheet-2 | #F0F0EC | #272932 |
| ink | #1B1B1F | #ECECEF |
| muted | #5F6068 | #A3A4AC |
| line (decorative hairline) | #E2E2DD | #33353E |
| field (inputs, interactive sheets) | #85868E | #75767F |
| pencil (action, insert, focus) | #2F62D8 | #8FAEFF |
| pencil-hover | #2550B8 | #B0C6FF |
| on-pencil | #FFFFFF | #16171B |
| proof red (removed words only) | #BF3328 | #FF8A7E |
| highlighter (behind ink) | #F2D43D | #544D2C |
| danger (errors: icon + "Error:" prefix + 2px border, never struck) | #B3261E | #FF9B8F |
| success | #1E7A4C | #6FD39E |
| warning | #8A5A00 | #E8B54A |
Marks never rely on colour alone: insertions are underlined or caret-marked, removals struck. Missing job keywords use
an empty marker in ink/pencil, not red. A rejected change shows the original in plain ink. The score is pencil blue.

Built (P6.4): hero split 6/6 at desktop (5/7 broke the headline into four lines); no kicker (craft-floor ban).
Paper stays white in dark mode too: documents are white paper under a lamp; only the desk and UI sheets go dark.
A job keyword missing from the resume is never highlighted yellow (yellow means matched); it gets a dotted underline.
Margin notes are hidden below 640 px (the description carries them).

## Risks to manage
Red marks can read as criticism of the user's writing: red only strikes removed words; insertions, actions and the
score use blue; copy stays warm. Editorial looks are common: keep the proof grammar functional (marks carry meaning)
rather than decorative serif styling.

## Unresolved
None at selection time.

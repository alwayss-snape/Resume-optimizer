---
name: Tailor · Resume Studio
description: Resume tailoring shown the way an editor marks a proof; every change struck, inserted, explained and reversible.
colors:
  desk: "#f6f6f3"
  sheet: "#ffffff"
  sheet-2: "#f0f0ec"
  hairline: "#e2e2dd"
  hairline-strong: "#c9c9c3"
  field-edge: "#85868e"
  graphite-ink: "#1b1b1f"
  muted-graphite: "#5f6068"
  blue-pencil: "#2f62d8"
  blue-pencil-deep: "#2550b8"
  on-pencil: "#ffffff"
  proof-red: "#bf3328"
  highlighter: "#f2d43d"
  danger: "#b3261e"
  success: "#1e7a4c"
  success-line: "#8fc4a5"
  warning: "#8a5a00"
  paper: "#ffffff"
  lamp-desk: "#16171b"
  lamp-sheet: "#1f2026"
  lamp-sheet-2: "#272932"
  lamp-ink: "#ececef"
  lamp-muted: "#a3a4ac"
  lamp-pencil: "#8faeff"
  lamp-proof-red: "#ff8a7e"
  lamp-highlighter: "#544d2c"
typography:
  display:
    fontFamily: "Schibsted Grotesk Variable, Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "62px"
    fontWeight: 700
    lineHeight: 1.02
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Schibsted Grotesk Variable, Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "40px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Schibsted Grotesk Variable, Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Schibsted Grotesk Variable, Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.625
  label:
    fontFamily: "Schibsted Grotesk Variable, Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    letterSpacing: "normal"
  proof:
    fontFamily: "Source Serif 4 Variable, Source Serif 4, Iowan Old Style, Georgia, serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.8
  margin-note:
    fontFamily: "Source Serif 4 Variable, Source Serif 4, Iowan Old Style, Georgia, serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.625
  figure:
    fontFamily: "Schibsted Grotesk Variable, Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "60px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.04em"
    fontFeature: "tnum"
rounded:
  hair: "1px"
  paper: "2px"
  sheet: "3px"
  control: "4px"
  full: "9999px"
spacing:
  xs: "8px"
  sm: "10px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  gutter-mobile: "16px"
  gutter-desktop: "32px"
  container: "1240px"
components:
  button-primary:
    backgroundColor: "{colors.blue-pencil}"
    textColor: "{colors.on-pencil}"
    rounded: "{rounded.control}"
    padding: "0 18px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.blue-pencil-deep}"
  button-primary-lg:
    backgroundColor: "{colors.blue-pencil}"
    textColor: "{colors.on-pencil}"
    rounded: "{rounded.control}"
    padding: "0 24px"
    height: "48px"
  button-secondary:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.graphite-ink}"
    rounded: "{rounded.control}"
    padding: "0 18px"
    height: "44px"
  button-secondary-hover:
    textColor: "{colors.blue-pencil}"
  button-ghost:
    textColor: "{colors.muted-graphite}"
    rounded: "{rounded.control}"
    padding: "0 18px"
    height: "44px"
  input:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.graphite-ink}"
    rounded: "{rounded.sheet}"
    padding: "0 14px"
    height: "44px"
  chip-found:
    textColor: "{colors.success}"
    rounded: "{rounded.sheet}"
    padding: "4px 10px"
  chip-missing:
    textColor: "{colors.graphite-ink}"
    rounded: "{rounded.sheet}"
    padding: "4px 10px"
  proposal-card:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.graphite-ink}"
    rounded: "{rounded.sheet}"
    padding: "24px"
  step-marker-current:
    backgroundColor: "{colors.blue-pencil}"
    textColor: "{colors.on-pencil}"
    rounded: "{rounded.full}"
    size: "22px"
---

# Design System: Tailor · Resume Studio

## Overview

**Creative North Star: "The Editor's Proof"**

Every screen is a copy editor's proof sheet turned into a working interface. White bond-paper sheets rest on a pale desk; graphite ink carries the words; one blue pencil does every action, every insertion and every focus ring; proof red strikes removed words and nothing else; a highlighter swipe lands behind job keywords the resume already matches. The marks are functional, not ornamental: each one says what changed, and the user can keep or reverse it.

Depth is physical. The desk, the sheets and the marks sit on separate planes, and the sheet that matters most is the brightest and highest. Sheets have a real paper edge and a soft contact shadow; they lift slightly when they take focus. Type is a newsroom pairing: a grotesk for the interface, a text serif for anything that is the resume itself, so documents read as documents and margin notes read as an editor's hand. Dark mode is the same proof under a desk lamp at night: the desk and the UI sheets go graphite, but document paper stays white.

The system rejects the SaaS "AI resume builder" look (colour gradients, sparkles, gauges, rounded glossy cards, glass) and the dark luxury look it replaces.

**Key Characteristics:**
- One action colour (blue pencil); red only ever means "removed".
- Square-cornered paper with real edges and contact shadows, not rounded cards.
- Grotesk for UI, serif for document and proof text, serif italic for margin notes.
- Marks never rely on colour alone: struck, underlined, swiped or dashed.
- Light and dark both designed; every text pair meets WCAG AA (4.5:1), every control boundary 3:1.

## Colors

A near-neutral paper-and-graphite field with three editor's marks: blue pencil, proof red and highlighter yellow.

### Primary
- **Blue Pencil** (light #2f62d8, lamp #8faeff): the only action colour. Primary buttons, focus outlines (2px, 3px offset), the caret colour, inserted words, the current step marker, the score figure and the score rule's needle. Deepens to Blue Pencil Deep (#2550b8, lamp #b0c6ff) on hover. A 9% wash (lamp 13%) marks selected segments and completed steps.

### Secondary
- **Proof Red** (light #bf3328, lamp #ff8a7e): strike marks through removed words, and nothing else. Never an error, never a missing keyword, never a score.
- **Highlighter** (#f2d43d at 55% behind text; lamp #544d2c): the swipe behind matched job keywords and the text selection colour. Text on it stays graphite ink.

### Tertiary
- **Danger** (light #b3261e, lamp #ff9b8f): errors, always with an icon and words and a border (2px for blocking errors), never a strike.
- **Success** (light #1e7a4c, lamp #6fd39e) with **Success Line** (#8fc4a5, lamp #2f5a44): found keywords, the target band on the score rule, passing states.
- **Warning** (light #8a5a00, lamp #e8b54a): changes to check and partial failures.

### Neutral
- **Desk** (light #f6f6f3, lamp #16171b): the page background.
- **Sheet** (light #ffffff, lamp #1f2026) and **Sheet 2** (light #f0f0ec, lamp #272932): UI sheets and recessed panels.
- **Paper** (#ffffff in both themes): document paper on the landing proof and the resume proof stack.
- **Graphite Ink** (light #1b1b1f, lamp #ececef) and **Muted Graphite** (light #5f6068, lamp #a3a4ac): text and secondary text.
- **Hairline** (light #e2e2dd, lamp #33353e) and **Hairline Strong** (#c9c9c3, lamp #4a4c57): decorative rules and dividers only.
- **Field Edge** (light #85868e, lamp #75767f): the 3:1 boundary on inputs, secondary buttons, chips and score-rule ticks.

### Named Rules
**The One Pencil Rule.** Blue pencil is the single action colour. If a second hue is doing an action, it is wrong.

**The Red Means Removed Rule.** Proof red strikes removed words and nothing else. Errors use danger with an icon and words; missing keywords use an empty marker in ink, never red.

**The Yellow Means Matched Rule.** The highlighter swipe sits only behind job keywords the resume already contains, with graphite text on it. A missing keyword gets a dashed or dotted treatment, never yellow; inserted or removed words are never stacked on the swipe.

**The White Paper Rule.** Document paper stays white in both themes, with its marks at their light-theme values; only the desk and UI sheets go dark.

## Typography

**Display Font:** Schibsted Grotesk Variable (with ui-sans-serif, system-ui)
**Body Font:** Schibsted Grotesk Variable
**Document Font:** Source Serif 4 Variable (with Iowan Old Style, Georgia)

**Character:** A newsroom grotesk, bold and tightly tracked at display sizes, does the interface; an optical-size text serif sets anything that is resume text, so the document under review always looks like a document.

### Hierarchy
- **Display** (700, 42px mobile to 56-62px desktop, 1.02, -0.035em): one page heading per screen (landing, Results, Report). Work screens use 40-48px.
- **Headline** (700, 32-40px, -0.025 to -0.03em): section heads such as "How it works" and "What the job asks for".
- **Title** (700, 22-24px, -0.02em): sub-sections and panel titles.
- **Body** (400, 15px UI text; 17-18px lead copy at max 46ch, 1.625): interface prose, in Graphite Ink or Muted Graphite.
- **Label** (500-600, 13px, sentence case): state badges, legend items, group counts, field labels at 14px.
- **Proof** (Source Serif 4, 400, 17px, 1.8; 16px at 1.7 in side-by-side view): resume text and the marked-up proof.
- **Margin Note** (Source Serif 4 italic, 14px, relaxed, muted): the editor's "why" beside a change, set off by a hairline left rule.
- **Figure** (Grotesk 700, 60-76px, -0.04em, tabular numerals, %-sign at 0.45em): the keyword-match figure in blue pencil.

### Named Rules
**The Document Reads As A Document Rule.** Resume words are always set in the serif; interface words never are, except the margin note.

**The Sentence Case Rule.** Interface labels are sentence case at normal tracking. No uppercase tracked kickers or eyebrows above headings.

**The Tabular Figures Rule.** Every number that counts or compares (scores, step numbers, counts, timers) uses tabular numerals.

## Layout

A centred page container of 1240px (1320px on the Review workbench, 760-820px for single-column forms) with 16px gutters on phones and 32px from 768px. The landing hero is a 12-column grid split 6/6 at desktop: words left, the tilted proof sheet right, stacking below 1024px. Review is a two-column workbench: proposal cards in a fluid column and a 340px side column holding the proof stack and live score; below 1024px the side column collapses into a sticky bottom bar, and the page reserves 6rem of scroll padding so the bar never covers the focused control.

Rhythm is loose between sections (64-112px), firm inside sheets: 20px card padding on phones, 24px from 768px, 24-32px on the score sheet; 16px between card parts; 10px between buttons in an action row. Group headers are a bold 15px label, a hairline running to the right, and a tabular count. Reading text stays within 38-60ch. Margin notes hide below 640px; the text carries them.

## Elevation & Depth

Depth is material: paper on a desk under one light source. A sheet has a bright catch on its top edge, two stepped edge lines below and to the right that read as the paper's thickness, a faint tonal falloff toward its bottom 14px, and a soft contact shadow. Interactive sheets lift on hover and focus (a deeper contact shadow plus a 2px rise where motion is allowed). Flat surfaces (the desk, recessed panels, rejected cards) carry no shadow at all. On the landing, depth is literal: desk, back sheet and front sheet sit in a CSS 3D space (1700px perspective) that tilts toward the cursor on a damped spring, with a slow blue-ink fluid field behind, masked away from the text column and kept at low contrast.

### Shadow Vocabulary
- **Sheet** (light: `inset 0 1px 0 rgb(255 255 255 / 0.95), 0 1px 0.5px #d3d3cb, 1px 2.5px 1px -0.5px #e1e1da, 2px 4px 1.5px -1.5px #e1e1da, 0 12px 28px -12px rgb(27 27 31 / 0.22)`): every resting UI sheet: proposal cards, score sheet, progress panel, proof stack.
- **Sheet Lift** (same edges, contact `0 26px 48px -18px rgb(27 27 31 / 0.32)`): a sheet under the pointer or holding focus.
- **Button Press** (`0 1px 2px rgb(27 27 31 / 0.12)`): primary buttons only, a pencil-weight shadow.
- **Lamp variants**: in dark the top catch drops to 6% white, the edges go near-black (#0d0e11, #2a2c34) and the contact deepens to 0.6-0.72 black.

### Named Rules
**The One Light Rule.** Shadows all fall down and to the right from one light. The most important sheet is the brightest and highest.

**The Real Edge Rule.** Elevation is a paper edge plus a contact shadow, never a blurred glow or a coloured shadow.

## Shapes

Paper is nearly square. Sheets, cards, inputs, chips and badges take a 3px corner; buttons and the segmented control 4px; miniature paper in the proof stack 2px; drawn bars 1px. Full rounding is kept for the round things an editor draws: step markers, numbered circles, progress dots and the score needle. Borders are 1px in Field Edge for interactive boundaries and Hairline for decoration; a dashed border means "not in" (a rejected card, a missing keyword, a change failing the fact check). Marks are drawn strokes (carets, strikes, ticks, arrows, the dashed route between steps) with round caps, never icon tiles.

## Components

### Buttons
Quiet and firm, like a stamped instruction.
- **Shape:** gently squared (4px), 44px tall (48px large), semibold 14px (15px large).
- **Primary:** blue pencil fill, white text (lamp: graphite text on light-blue pencil), pencil-weight shadow; hover deepens to Blue Pencil Deep. One per decision area.
- **Secondary:** sheet fill, Field Edge 1px border, ink text; hover turns border and text blue pencil.
- **Ghost:** muted text, no box; hover goes to ink with an underline.
- **Focus / Disabled:** 2px blue-pencil outline at 3px offset; disabled at 50% opacity with a not-allowed cursor. Colour transitions at 150ms.

### Chips
- **Style:** 3px corners, 13px text, 4px 10px padding. Found keywords: Success Line border, success text, a check stroke. Missing keywords: dashed Field Edge border, ink text, an empty ring marker, with "· required" in muted text when the job requires it.
- **State badges:** the same shape on proposal cards, toned by state (pass, unchanged, check, dropped, failed).

### Cards / Containers
- **Corner Style:** 3px.
- **Background:** Sheet, with the sheet's tonal falloff.
- **Shadow Strategy:** Sheet at rest, Sheet Lift on hover and focus (see Elevation & Depth).
- **Border:** 1px hairline at 55% strength; focus turns it blue pencil.
- **Internal Padding:** 20px, 24px from 768px.
- **Rejected state:** the sheet drops onto the desk: no shadow, dashed Field Edge border, desk fill, original text in ink, the italic serif word "stet" underlined dotted in blue pencil, and an Undo.

### Inputs / Fields
- **Style:** 3px corners, 1px Field Edge border, sheet fill, 15px text, 44px tall; textareas resize vertically with relaxed leading. Labels sit above in 14px medium ink.
- **Focus:** border turns blue pencil plus the global 2px pencil outline; hover darkens the border to ink.
- **Error:** danger text with an alert icon and words; blocking errors use a 2px danger border.

### Navigation
- **Header:** a hairline under a 1240px bar holding the "Tailor" wordmark (24px bold grotesk with a drawn blue caret beneath it), the stepper and a settings popover.
- **Stepper:** 22px round markers joined by 24px rules. Done: pencil wash with a check; current: solid pencil with the number and bold ink label; ahead: Field Edge ring and muted text. Reached steps are buttons back. Below 768px it collapses to "Step 2 of 4 · Label" with a back link.

### Proof Marks (signature)
The grammar every screen shares. Removed words: proof red with a 1.5px strike. Inserted words: blue pencil with a 2px underline at 0.2em offset. Matched job keyword: semibold ink with an angled highlighter swipe filling the lower 72% of the line. A legend ("How to read the marks") sits above any marked list. On the landing proof the same marks draw themselves: the strike sweeps across in 0.55s, a caret draws and the inserted word rises, the swipe fills left to right, a bordered margin note floats in at a slight angle.

### Score Rule (signature)
The match rate as an editor's rule, never a gauge: a 0-100 baseline with 21 ticks in Field Edge, the target band as a pale success block with a Success Line ring and its label, the earlier rate as a strong-hairline ghost mark, and the current rate as a 3px blue-pencil needle that slides to place (0.9s, ease-out-expo). Above it, the figure counts up in blue pencil with a "+n pts" badge.

### Proof Stack (signature)
A miniature resume on three stacked, slightly rotated paper sheets, one bar per proposed change: ink with a pencil tick (going in), blue pencil (your words), pale and struck in proof red (rejected), dashed danger outline (fails the fact check). Bars re-colour as decisions change; a legend below repeats the same fixed colours.

### Progress Panel
A sheet with a bold title, a tabular seconds counter, a 3px hairline track with a blue-pencil stroke running across (1.6s loop; static and faint under reduced motion), and a list of steps: done in muted text with a success check, the running one in ink with a pulsing pencil dot.

## Do's and Don'ts

### Do:
- **Do** use blue pencil (#2f62d8, lamp #8faeff) for every action, insertion, caret and focus ring, and for nothing decorative.
- **Do** show every change as a mark that survives without colour: strike for removed, underline or caret for inserted, swipe for matched, dashed for "not in".
- **Do** set resume and proof text in Source Serif 4 at 17px with 1.8 leading, and the reason for a change as a serif-italic margin note.
- **Do** put working content on square-cornered sheets (3px) with the Sheet shadow, and lift them with Sheet Lift on hover and focus.
- **Do** keep document paper white in dark mode; only the desk and UI sheets go dark.
- **Do** give every motion a still state under prefers-reduced-motion: drawn marks appear at once, the needle sits in place, the running stroke turns static.
- **Do** use tabular numerals for every score, count and timer.

### Don't:
- **Don't** use proof red for errors, warnings, missing keywords or a falling score; errors use danger with an icon and words, never a strike.
- **Don't** highlight a missing keyword yellow, or put blue or red text on the yellow swipe.
- **Don't** use decorative colour gradients, sparkles, glow, glass or blurred translucent panels; the only gradients are the paper's own tonal falloff, the highlighter swipe and the hero's ink field.
- **Don't** round cards past 4px or float them as glossy SaaS tiles.
- **Don't** draw the score as a gauge, ring or dial; it is a rule with a needle.
- **Don't** put uppercase tracked kickers or eyebrows above headings, or show icons inside coloured tiles; marks are drawn strokes.
- **Don't** bring back the dark luxury look: dark mode is a desk lamp on paper, not a black-and-gold surface.

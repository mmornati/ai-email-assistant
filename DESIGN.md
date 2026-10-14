---
name: AI Mail Assistant
description: Transit Line Map. The inbox drawn as a metro network; mail rides one line and alights at its tag.
colors:
  signage-black: "#121417"
  panel-lift: "#1f2328"
  ink-secondary: "#474b51"
  ink-tertiary: "#6b6f75"
  signal-red: "#e4002b"
  signal-ink: "#ffffff"
  focus-blue: "#0072ce"
  enamel: "#f4f2ec"
  enamel-deep: "#e9e6dc"
  enamel-worn: "#dcd8cb"
  rule-line: "#cfcabc"
  panel-ink-secondary: "#b9bcc0"
  line-action: "#e4002b"
  line-alerts: "#ff6a13"
  line-github-admin: "#5b6770"
  line-meeting-invite: "#0072ce"
  line-meeting-notes: "#41b6e6"
  line-shares: "#009b8d"
  line-admin: "#8c5a2b"
  line-internal-comms: "#7a3e9d"
  line-newsletter: "#ffb500"
  line-promo: "#e8559a"
  line-fyi: "#00a650"
  line-backlog: "#a3a39c"
typography:
  display:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(2.6rem, 4.4vw, 4.1rem)"
    fontWeight: 800
    lineHeight: 0.94
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(2.2rem, 4.6vw, 3.6rem)"
    fontWeight: 800
    lineHeight: 1.02
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, sans-serif"
    fontSize: "1.45rem"
    fontWeight: 700
    lineHeight: 1.15
  body:
    fontFamily: "Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.6
    fontFeature: "\"tnum\" 1"
  label:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.12em"
  data:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "1.15rem"
    fontWeight: 600
    lineHeight: 1
    fontFeature: "\"tnum\" 1"
  command:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "0.98rem"
    fontWeight: 400
    lineHeight: 1.85
rounded:
  xs: "5px"
  sm: "6px"
  md: "12px"
  lg: "16px"
  xl: "18px"
  pill: "999px"
spacing:
  xs: "10px"
  sm: "14px"
  md: "22px"
  lg: "40px"
  section: "clamp(72px, 10vw, 128px)"
  container: "1280px"
components:
  button-primary:
    backgroundColor: "{colors.enamel}"
    textColor: "{colors.signage-black}"
    typography: "{typography.title}"
    rounded: "{rounded.md}"
    padding: "14px 18px 13px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.enamel}"
    rounded: "{rounded.md}"
    padding: "14px 18px 13px"
  button-panel:
    backgroundColor: "{colors.signage-black}"
    textColor: "{colors.enamel}"
    rounded: "{rounded.md}"
    padding: "14px 20px"
  button-panel-hover:
    backgroundColor: "{colors.panel-lift}"
  line-bullet:
    textColor: "{colors.signal-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0.32em 0.6em 0.3em"
  station-sign:
    backgroundColor: "{colors.signage-black}"
    textColor: "{colors.enamel}"
    rounded: "{rounded.xl}"
    padding: "clamp(22px, 2.4vw, 36px)"
  departures-board:
    backgroundColor: "{colors.signage-black}"
    textColor: "{colors.enamel}"
    rounded: "{rounded.lg}"
    padding: "8px 22px 6px"
  enamel-panel:
    backgroundColor: "{colors.enamel}"
    textColor: "{colors.signage-black}"
    rounded: "{rounded.lg}"
  nav-link:
    textColor: "{colors.signage-black}"
    rounded: "{rounded.pill}"
    padding: "10px 12px"
  nav-link-hover:
    backgroundColor: "{colors.enamel-deep}"
---

# Design System: AI Mail Assistant

## Overview

**Creative North Star: "The Transit Line Map"**

The inbox is a metro network. Mail rides one line from the Inbox terminus through Rules, Sweep and Classify, and alights at one of twelve tag terminals; the model is an express spur that is lit only when the rules cannot route. Every surface (the landing page, the demo console, the MkDocs skin and the canvas film) is drawn in the same transit-authority vocabulary: an off-white enamel ground, signage-black enamel panels, rounded-rect station signs, roundel station marks, and one flat line colour per tag.

The world is wayfinding, not decoration. Thick rounded strokes carry meaning (a coloured line is a tag; the black trunk is the run; the red tail is mail that waits for a person). Type is split by job exactly as a transit authority splits it: condensed signage for names and headings, a legibility face for reading, a monospace only where something is typed or counted. Numbers on a page are instrument readouts of one demo run, not marketing figures.

Density is calm and generous on the landing page (one idea per section, long section breaks) and tighter in the demo console, where panels sit in a 7/5 grid like a control room.

**Key Characteristics:**
- Enamel ground, signage-black panels, flat colour, no soft drop shadows.
- One line colour per tag; the colour is the tag everywhere it appears.
- Signal red is held back for Action, "Waiting for you" and refusals.
- Thick round-capped strokes, straight segments, no curves.
- Label changes snap like a destination blind; that overshoot step is the only motion signature.
- Dark mode inverts the enamel: the ground goes near-black and the panels go enamel.

## Colors

A transit authority's palette: a neutral enamel-and-black base carrying twelve saturated line colours, with one reserved alarm red.

### Primary
- **Signage Black** (signage-black): Body text, headings, the trunk line, roundel strokes, and the background of every enamel panel (station sign, departures board, terminal, step counters, the closing terminus band). In dark mode it swaps roles with Enamel.
- **Panel Lift** (panel-lift): The hover state of a black panel button; one step lighter, never a glow.

### Secondary
- **Signal Red** (signal-red): The alarm. Used for the Action line, the "Waiting for you" terminal and its tail of the trunk, the counters that report waiting mail, the waiting-row tint in the demo inbox (7% mix), and refusal signage in the safety section. White text (signal-ink) on red fills.

### Tertiary
- **The twelve lines** (line-action through line-backlog): One flat colour per AI/ tag, used for line strokes on the map, tag bullets, board swatches and figure-caption roundels. Action shares Signal Red by design. Newsletter, Meeting/Notes, Alerts, Backlog and Promo are light enough that their bullets carry signage-black text; the rest carry white.
- **Focus Blue** (focus-blue): Keyboard focus rings and link-hover underline colour; it is the Meeting/Invite line colour and the bar of the logo roundel.

### Neutral
- **Enamel** (enamel): The page ground and the face of station marks drawn on lines.
- **Enamel Deep** (enamel-deep): Tinted fills: caption strips, segmented-control tracks, due-date chips, docs code blocks, nav hover.
- **Enamel Worn** (enamel-worn): Row dividers inside panels and scrollbar thumbs.
- **Rule Line** (rule-line): 1px hairlines, panel borders, image outlines, the dark (unused) express spur in the timetable.
- **Ink Secondary / Ink Tertiary** (ink-secondary, ink-tertiary): Lead paragraphs and supporting copy; timestamps, column headers, dim numbers.
- **Panel Ink Secondary** (panel-ink-secondary): Secondary copy on black panels.

### Named Rules
**The Signal Rule.** Signal red means a person must act: the Action line, "Waiting for you", and refusals. It is never a brand accent, a button fill, or emphasis.

**The One Line, One Colour Rule.** A tag's line colour is its identity across map, bullet, board swatch and film. Never reuse a line colour for anything that is not that tag (Meeting/Invite blue doubling as focus is the single sanctioned overlap).

## Typography

**Display Font:** Barlow Semi Condensed (with Arial Narrow, sans-serif), weights 600/700/800
**Body Font:** Atkinson Hyperlegible (with system-ui, sans-serif), 400/700 and italic
**Label/Mono Font:** JetBrains Mono (with ui-monospace, Menlo), 400/600

**Character:** Condensed signage that reads at a glance over a face designed for low-vision legibility; the mono is an instrument, not a style.

### Hierarchy
- **Display** (800, clamp(2.6rem, 4.4vw, 4.1rem), 0.94): The headline on the station sign only; set in two stacked lines.
- **Headline** (800, clamp(2.2rem, 4.6vw, 3.6rem), 1.02): Section headings, balanced wrap. The terminus band goes up to clamp(2.4rem, 5vw, 4rem).
- **Title** (700, 1.15 to 1.45rem): Station names in the line sequence, signage rows, timetable runs, button labels (1.05rem).
- **Body** (400, 1.0625rem, 1.6): Reading copy, max 66ch; leads at 1.14rem in ink-secondary. Tabular figures on.
- **Label** (600 to 700, 0.78 to 0.98rem, 0.04 to 0.14em, uppercase): Board captions, column headers, panel meta, tag bullets (bullets are not uppercase). These are signage on a board or column, attached to the data they name.
- **Data** (600, 1 to 1.6rem, JetBrains Mono, tabular): Counts on the board, the map and the timetable.
- **Command** (400, 0.84 to 0.98rem, 1.6 to 1.85): Terminal blocks and inline `code`.

### Named Rules
**The Mono Is An Instrument Rule.** JetBrains Mono appears only for commands a person types and numbers a run produced. Never for headings, labels, or decoration.

**The Readout Rule.** Every number on a page is a readout of `docs/assets/demo/run.json` and must cross-check against it; counts rendered by script come from `tally()`, and any count written into prose must match the same run.

## Layout

A centred container of min(1280px, 100% - 32px) on the landing page and min(1400px, 100% - 32px) in the demo console. Sections open with a 5/7 intro grid (heading left, lead right, bottom-aligned) and are separated by clamp(72px, 10vw, 128px). Content grids are asymmetric fractions (5/7, 7/5, 4/8); the demo console is a 7/5 grid of panels with 22px gutters.

The hero places the station sign over the upper-left 42% of the line map, as if the sign stands on the Inbox terminus. Below 1100px the sign stacks and the map becomes an in-car strip map: a vertical 8px trunk with roundel stops and the red terminal last. The six-station line sequence turns vertical below 900px; most two-column grids collapse to one at 900px, secondary navigation drops at 760px.

## Elevation & Depth

Flat enamel. Depth comes from tone (black panel on enamel ground, enamel panel with a 1px rule border) and from line weight, not from shadows. The only `box-shadow` values in the build are inset or ring strokes standing in for borders: the ghost button's 2px inset outline, the hollow swatch and dark-spur outlines, and the double-ring interchange roundel for model stations (0 0 0 4px enamel, 0 0 0 7px trunk). Hover lifts a button 2px with translateY; it does not add a shadow. The sticky top bar is 92% enamel with a light backdrop blur so the map shows through on scroll.

### Named Rules
**The Flat Enamel Rule.** Panels are flat enamel: no soft drop shadows, no gradients. If a surface needs separation, give it a tone change or a 1px rule.

## Shapes

Rounded-rect signs and perfect circles. Panels and signs use generous radii (16 to 18px), buttons and pictogram tiles 12px, small chips 5 to 6px, and tag bullets, nav links and segmented controls are full pills. Station marks are roundels: an enamel circle with a 4 to 5px black (or line-coloured) ring; interchanges are pills spanning several lines. Lines are 8 to 10px strokes with round caps and joins, built from straight segments: branches leave the trunk at right angles and the express spur rises and returns on near-diagonal legs. No curves. Screenshots carry a 14px radius and a 1px inset rule outline.

## Components

### Buttons
Signage plates: condensed, bold, compact.
- **Shape:** gently rounded (12px).
- **Primary:** enamel plate with signage-black text and a black roundel glyph, placed on black panels (station sign, terminus band).
- **Ghost:** transparent with a 2px inset outline at 35% panel ink, solid on hover.
- **Panel:** signage-black plate on the enamel ground; hover moves to Panel Lift.
- **Hover / Focus:** translateY(-2px) over .25s on the ease-out curve; focus is a 3px Focus Blue outline offset 3px.

### Line Bullets (chips)
- **Style:** full pill filled with the tag's line colour, label type at 0.78rem 700; white text, or signage-black on the five light lines.
- **State:** a bullet that changes label animates with the destination-blind step.

### Cards / Containers
- **Station sign / departures board / terminal:** signage-black, 16 to 18px radius, no border, padding 22 to 36px. Board rows divide at 10% panel ink; captions at 16%.
- **Enamel panel (demo console):** enamel fill, 1px rule border, 16px radius, header row 14px 18px with a 1px rule underline and uppercase meta on the right.
- **Shadow Strategy:** none (see Elevation & Depth).

### Navigation
Top bar 64px, sticky, logo roundel plus wordmark in 800 signage type; links are 700 signage pills that tint to Enamel Deep on hover; the GitHub link is a black pill. The footer terminus band lists links each led by a small hollow roundel. In the docs, the active nav item carries the same hollow roundel and h2 headings are led by a ringed station mark.

### Segmented Control
Enamel Deep pill track with 4px inset; the pressed option becomes a black pill. Used for the film's language switch.

### The Line Map (signature)
An SVG drawn from the run: a black 10px trunk from Inbox to Validate, a 10px Signal Red tail to "Waiting for you", one 8px line per tag branching up (rules) or down (model) to its terminal, each terminal a roundel ringed in its line colour with a mono count. The express spur is hollow (an enamel core inside a black casing) while idle and drawn solid once the run has escalated mail; when nothing escalates it drops to 22% opacity and stays dark. Messages travel as small enamel dots; mail bound for Action or waiting rides as a red dot.

### Motion
**The Destination Blind Rule.** Label and count changes use one step: a clip-and-drop from above on cubic-bezier(.34, 1.56, .64, 1) over .42 to .5s, overshooting and settling like a roller blind. It is the only motion signature; everything else is a plain ease-out (cubic-bezier(.16, 1, .3, 1)) and all of it stops under reduced motion.

## Do's and Don'ts

### Do:
- **Do** draw every tag in its own line colour, and only that tag.
- **Do** keep Signal Red for Action, "Waiting for you" and refusals.
- **Do** separate surfaces with tone or a 1px Rule Line, never a soft shadow.
- **Do** mark stations with roundels and interchanges with pills; draw lines as 8 to 10px round-capped straight segments.
- **Do** source every on-page number from `docs/assets/demo/run.json` and cross-check prose against it.
- **Do** animate label changes with the destination-blind step and honour prefers-reduced-motion.
- **Do** invert enamel and panel in dark mode rather than inventing a second palette.

### Don't:
- **Don't** use JetBrains Mono for anything but commands and data.
- **Don't** add soft drop shadows or gradients to the enamel panels.
- **Don't** use Signal Red as a brand accent, button fill or emphasis colour.
- **Don't** draw curved lines or introduce a second easing signature.
- **Don't** write a figure into the page that the demo run does not produce.

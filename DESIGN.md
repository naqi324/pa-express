---
name: Prior Auth Express
description: A gridded clinical record for prior authorization review, where every criterion is traced to the exact words in the chart.
colors:
  surface: "#fbfcfd"
  paper: "#ffffff"
  sunk: "#eef1f4"
  ink: "#1a2530"
  ink-2: "#465563"
  ink-3: "#5a6774"
  rule: "#d5dbe1"
  rule-strong: "#b4bec8"
  field-border: "#7d8a96"
  action: "#2f6f9f"
  action-deep: "#245a82"
  action-wash: "#e8f1f8"
  action-wash-2: "#d4e5f2"
  flag: "#c2410c"
  flag-deep: "#a8370a"
  flag-wash: "#fdf0e9"
  binder: "#1a2530"
  binder-tab: "#26333f"
  binder-text: "#aab6c2"
  binder-rule: "#4a5a69"
  binder-hover: "#33424f"
  binder-focus: "#8fc0e6"
typography:
  display:
    fontFamily: "'Atkinson Hyperlegible Next Variable', 'Atkinson Hyperlegible Next', system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "'Atkinson Hyperlegible Next Variable', 'Atkinson Hyperlegible Next', system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "'Atkinson Hyperlegible Next Variable', 'Atkinson Hyperlegible Next', system-ui, sans-serif"
    fontSize: "1.1875rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  lead:
    fontFamily: "'Atkinson Hyperlegible Next Variable', 'Atkinson Hyperlegible Next', system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "'Atkinson Hyperlegible Next Variable', 'Atkinson Hyperlegible Next', system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  small:
    fontFamily: "'Atkinson Hyperlegible Next Variable', 'Atkinson Hyperlegible Next', system-ui, sans-serif"
    fontSize: "0.84375rem"
    fontWeight: 600
    lineHeight: 1.2
  label:
    fontFamily: "'Atkinson Hyperlegible Next Variable', 'Atkinson Hyperlegible Next', system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.3
  numeric:
    fontFamily: "'Atkinson Hyperlegible Next Variable', 'Atkinson Hyperlegible Next', system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.5
    fontFeature: "tnum"
  code:
    fontFamily: "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  hairline: "1px"
  base: "2px"
  tab: "3px 3px 0 0"
spacing:
  space-1: "0.25rem"
  space-2: "0.5rem"
  space-3: "0.75rem"
  space-4: "1rem"
  space-5: "1.5rem"
  space-6: "2rem"
  space-7: "3rem"
  control-height: "2.125rem"
  control-height-small: "1.75rem"
  page-inline: "clamp(1rem, 2.5vw, 2rem)"
components:
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "{colors.paper}"
    typography: "{typography.small}"
    rounded: "{rounded.base}"
    padding: "0 0.875rem"
    height: "{spacing.control-height}"
  button-primary-hover:
    backgroundColor: "{colors.action-deep}"
    textColor: "{colors.paper}"
  button-primary-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.small}"
    rounded: "{rounded.base}"
    padding: "0 0.875rem"
    height: "{spacing.control-height}"
  button-secondary-hover:
    backgroundColor: "{colors.action-wash}"
    textColor: "{colors.ink}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.action-deep}"
    typography: "{typography.small}"
    rounded: "{rounded.base}"
    padding: "0 0.5rem"
    height: "{spacing.control-height}"
  button-small:
    typography: "{typography.label}"
    padding: "0 0.625rem"
    height: "{spacing.control-height-small}"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.base}"
    padding: "0.375rem 0.5625rem"
    height: "{spacing.control-height}"
  box:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.numeric}"
    padding: "0.375rem 0.625rem 0.5rem"
  code-met:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.base}"
    padding: "0 0.4375rem"
    height: "1.375rem"
  code-not-met:
    backgroundColor: "{colors.flag}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.base}"
    padding: "0 0.4375rem"
    height: "1.375rem"
  code-insufficient:
    backgroundColor: "{colors.flag-wash}"
    textColor: "{colors.flag-deep}"
    typography: "{typography.label}"
    rounded: "{rounded.base}"
    padding: "0 0.4375rem"
    height: "1.375rem"
  code-action:
    backgroundColor: "{colors.action-wash}"
    textColor: "{colors.action-deep}"
    typography: "{typography.label}"
    rounded: "{rounded.base}"
    padding: "0 0.4375rem"
    height: "1.375rem"
  divider-tab:
    backgroundColor: "{colors.sunk}"
    textColor: "{colors.ink-2}"
    typography: "{typography.small}"
    rounded: "{rounded.tab}"
    padding: "0 0.875rem"
    height: "2.25rem"
  divider-tab-selected:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
  app-tab:
    backgroundColor: "{colors.binder-tab}"
    textColor: "{colors.binder-text}"
    typography: "{typography.small}"
    rounded: "{rounded.tab}"
    padding: "0 0.875rem"
    height: "2.25rem"
  app-tab-current:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
  toast:
    backgroundColor: "{colors.binder}"
    textColor: "{colors.surface}"
    rounded: "{rounded.base}"
    padding: "0.75rem 0.5rem 0.75rem 0.875rem"
    width: "min(26rem, calc(100vw - 2rem))"
  toast-error:
    backgroundColor: "{colors.flag-wash}"
    textColor: "{colors.ink}"
---

# Design System: Prior Auth Express

## Overview

**Creative North Star: "The Gridded Clinical Record"**

Prior Auth Express looks like a printed clinical record that the nurse fills in. Each case is a ruled form. Policy criteria run down the rows. The submitted documents run across the columns. Each cell holds a charting-ink entry that shows where the evidence lives. The page is white and cool. Text is blue-black ink. Thin gray rules make every box, row, and column. Blue marks action and selection. Orange marks only the exceptions.

Density is high and calm. A nurse uses this screen for a full shift. The layout keeps fixed stations: the app bar, the patient banner, the lifecycle stamps, the grid, the decision column, and the sign-off strip. Each station is always in the same place. Empty states are designed absence: a blank ruled box or a dashed box that names what is missing. It is not an illustration.

The system refuses the generic dashboard. It has no KPI tiles, no card stacks, and no pill soup. Depth comes from rules and tonal fills, not from shadows.

**Key Characteristics:**
- Ruled cells and boxed fields, with small caption labels printed inside each box.
- Achromatic text. Normal values stay in ink. Only abnormal values take color.
- One legible sans with tabular numerals for every number, date, code, and clock.
- Square corners (2px), 1px rules, flat surfaces.
- Short state tints (120 to 200 ms). Instant swaps under reduced motion.

## Colors

A cool paper-and-ink palette with one blue for action and one orange for abnormal-flag marks.

### Primary
- **Charted Blue** (action): Primary buttons, the selected-tab top bar, focus rings, the active grid cell ring, caret and accent color, and the evidence highlight underline. It means "you can act here" or "this is selected".
- **Deep Charted Blue** (action-deep): Primary hover, link text, quiet-button text, and blue chip text.
- **Blue Wash** (action-wash): Hover fills, lit rows and columns in the grid, the next lifecycle stamp, and the active evidence quote.
- **Blue Wash Strong** (action-wash-2): The active cell, lit column headers, text selection, and the highlighted quote inside a document.

### Secondary
- **Flag Orange** (flag): Abnormal-flag marks only. The Not met chip fill, the gap ring, the gap flag icon, invalid field borders, flagged notices, the backend-down badge.
- **Deep Flag** (flag-deep): Flag text on light fills: Insufficient chip text, the urgent SLA clock, field errors, the "Field blank in record" caption.
- **Flag Wash** (flag-wash): The fill behind flagged notices, the Insufficient chip, error toasts, and a quote highlight that falls short of its criterion.

### Neutral
- **Record Paper** (surface): The page background and the selected-tab fill, so the selected tab joins the page below it.
- **Box White** (paper): Boxes, tables, grid frames, inputs, and secondary buttons sit on this. It is one step lighter than the page.
- **Sunk Gray** (sunk): Table and grid header rows, unselected divider tabs, disabled controls, and the sign-off title cell.
- **Charting Ink** (ink): All body text and values. Also the evidence dot.
- **Ink 2** (ink-2): Secondary text, header-row text, and rationale copy.
- **Ink 3** (ink-3): Caption labels, hints, placeholders, and pending stamps.
- **Rule** (rule): Hairline rules between rows, cells, and blocks.
- **Strong Rule** (rule-strong): Box outlines, grid frames, header-row borders, and tab edges.
- **Field Border** (field-border): Input and button outlines, so controls read darker than plain boxes.
- **Binder** (binder), **Binder Tab** (binder-tab), **Binder Text** (binder-text): The dark app bar, its unselected tabs, and its muted text. Binder shares the ink value on purpose: the bar is the record's dark cover.
- **Binder Rule** (binder-rule): The outline of the engine button on the dark bar.
- **Binder Hover** (binder-hover): The hover fill of an unselected app tab.
- **Binder Focus** (binder-focus): The focus ring on the dark bar and the icon on the dark toast. Charted Blue is too dark to read on the binder.

### Named Rules
**The Abnormal-Only Rule.** Color never marks a normal value. Met stays in ink. Only Not met, Insufficient, overdue, and urgent take orange.

**The Two-Signal Rule.** Blue means action or selection. Orange means exception. No third accent exists. Do not add green for success.

## Typography

**Body Font:** Atkinson Hyperlegible Next (variable, installed locally; system-ui fallback)
**Label/Mono Font:** ui-monospace stack, for code, prompts, and payloads only

**Character:** One legible workhorse sans carries every role. Hierarchy comes from weight and a tight size step (ratio about 1.14), not from a second face.

### Hierarchy
- **Display** (700, 1.625rem, 1.2): Page titles, for example "PA-1001 — Patricia Nowak" and "Worklist".
- **Headline** (700, 1.375rem, 1.2): Empty-state titles and large section heads.
- **Title** (700, 1.1875rem, 1.2): Block titles inside a tab panel.
- **Lead** (700, 1.0625rem): Section titles and the wordmark (the wordmark is 800).
- **Body** (400, 0.9375rem, 1.5): Running text, table cells, and box values. Record text is 0.84375rem at 1.6 line height, capped at 88ch. Lead copy caps at 72ch.
- **Small** (600, 0.84375rem): Buttons, tabs, form labels, and fact-list terms.
- **Label** (600, 0.75rem, 1.3): Caption labels inside boxes, header rows, chips, and the legend. Sentence case. No uppercase and no letter spacing.

### Named Rules
**The Tabular Figures Rule.** Every number, date, time, ID, code, and countdown uses tabular numerals, so columns of figures align.

**The Caption-Inside Rule.** A caption label names the value in its own box. It never floats above a heading as a label.

## Layout

The page frame is centered, up to 100rem wide, with fluid side padding (page-inline) and space-5 above and space-7 below. A page head holds the title and one muted line on the left and actions on the right, over a 1px rule.

The case workspace stacks these stations, top to bottom:

1. **App bar with tabs.** A dark binder bar holds the wordmark, the engine button, the version, and the demo note "Demo — synthetic data, no PHI". Below it, divider tabs name Worklist (with a count), New request, the open case, and Engine at the far end.
2. **Patient banner.** One row of boxed fields: Member ID, Date of birth, Plan, Requesting provider, Service codes, Setting, Urgency, and last "Decision due" with the SLA countdown under the date.
3. **Lifecycle stamp strip.** Five equal cells: Received, Analysis started, Analysis completed, Decision, Provider letter. Done stamps read in ink. The next stamp takes the blue wash with a 2px blue underline.
4. **Work area.** The main column (about 9/12) holds the in-page divider tabs, then the criteria × documents grid, its legend, a two-pane inspector (detail pane 5/12, document pane 7/12), and the evidence sources list. The decision column (fixed 21.5rem, about 3/12) is sticky and holds the recommendation and the actions.
5. **Sign-off strip.** Full width at the bottom. A sunk title cell ("Sign-off") beside boxed fields: Reviewer, Disposition, Authorization valid, Signed at, Provider letter.

Spacing uses the space-1 to space-7 scale (0.25rem to 3rem). Blocks inside a tab panel sit space-5 apart, split by a 1px rule. Controls are 2.125rem tall (1.75rem small).

**Responsive.** Below 68rem the work area becomes one column, in the order main then aside, and the decision column stops being sticky. Below 60rem the inspector panes stack. Below 48rem the lifecycle strip becomes two columns and the sign-off strip stacks. Below 40rem the grid columns narrow and the grid scrolls sideways inside its frame. Boxed fields reflow with an auto-fit grid (minimum 9.5rem per box).

## Elevation & Depth

The system is flat. Depth comes from tonal steps (surface, paper, sunk) and from 1px rules. Sticky header rows and the sticky criterion column stay on top by fill color, not by shadow.

### Shadow Vocabulary
- **Toast lift** (`box-shadow: 0 6px 18px -8px rgb(26 37 48 / 28%), 0 1px 3px rgb(26 37 48 / 10%)`): Only on toasts, which float over the page. It is a soft, centered shadow, not an offset block.

Focus and selection use inset marks, not shadows: the active cell has a 2px inset blue ring, and keyboard focus adds a 2px paper gap inside it. Lit column headers and the next lifecycle stamp carry a 2px inset bottom underline in Charted Blue (`box-shadow: inset 0 -2px 0`).

**The Selection Underline Rule.** A 2px inset bottom underline in the action color marks a lit column header and the next lifecycle stamp. It is the same family as the 3px top bar on a selected tab. Side stripes stay banned.

### Named Rules
**The Ruled-Not-Raised Rule.** Surfaces never lift. If a region needs separation, give it a rule or a tonal fill.

## Shapes

Corners are nearly square: 2px on boxes, buttons, inputs, chips, notices, and toasts. Divider tabs round only their top corners (3px). The evidence dot and skeleton bars use 1px. The only circle is the gap ring. Borders are 1px everywhere. Boxed fields share their rules like a printed form: the group draws the top and left edges, and each box draws its right and bottom edges. Designed absence uses a 1px dashed strong rule.

## Components

### Buttons
- **Shape:** Nearly square (2px), 2.125rem tall, 600 weight small text, optional leading icon.
- **Primary:** Charted blue fill with white text. Hover goes to deep blue. Active goes to ink.
- **Secondary:** White box with a field-border outline. Hover takes the blue wash and a blue outline.
- **Quiet:** No outline, deep blue text, blue wash on hover. Used for links such as "Back to worklist" and "View policy".
- **Disabled:** Sunk fill, strong rule, ink-3 text.
- **Focus:** 2px blue outline with a 2px offset on every control.

### Status chips (codes)
- **Style:** Compact 1.375rem tags with a 1px border, 700 label text, and a small icon.
- **Criterion verdicts:** Met is white with ink text and a check. Not met is solid flag orange with white text and a cross. Insufficient is flag wash with deep flag text and a question mark.
- **Case status:** Needs review takes the blue wash. Approved, Pended, and Referred to MD stay in ink. Received and Analyzing are plain text. Analysis failed takes the soft flag.

### Boxed fields
The signature form element. A caption label sits inside the top of a ruled box, with the value below in 600 weight and tabular numerals. Used by the patient banner, the sign-off strip, and form summaries. Boxes can span two columns or the full row.

The engine connection choice uses the same shared rules as a radio group. Each box holds a radio, the connection name, and a one-line summary. The selected box takes the blue wash and a 1px inset blue ring. A readiness note shows only when the connection is not ready.

### Ruled tables
Full-width tables on white with 1px row rules. The header row is sunk, sticky, and set in 700 caption text. Group header rows (for example "Standard — 7-day decision 3") use the page fill and a strong rule. The worklist uses this pattern with a segmented filter above it.

### Criteria × documents grid
Criterion text on the left (sticky, indented by depth for nested criteria, with any "1 or more of the following" logic in caption text), a Verdict column of chips, then one column per document with its date. A cell holds an evidence dot (a 10px ink square) with a count when there is more than one quote. The gap ring (a 2px orange circle) marks a quote that falls short of its criterion. The gap flag (an orange flag icon) marks a row that needs attention and bolds its text. Arrow keys move a crosshair: the active cell gets the strong wash and a blue ring, and its row and column light in the blue wash. When evaluation completes, marks are drawn into the blank grid over 200 ms with a capped stagger. A lit column header takes the strong blue wash and a 2px blue bottom underline. A legend under the grid decodes every mark.

### Evidence quote
A ruled box holding the verbatim quote in curly quotes, with a source link below (document name and date, underlined in deep blue). The active quote takes the blue wash and a blue border. A flagged quote takes an orange border. When a flagged quote contains a run of underscores, the caption "Field blank in record" appears with a flag icon in deep flag.

### Detail and document panes
Two panes inside one ruled frame. The detail pane shows the criterion, its chip, confidence, rationale, and quotes. The document pane shows the document title over a caption line, then the text with the quote highlighted (strong blue wash with a 2px blue underline, or flag wash with an orange underline for a gap).

### Divider tabs
Tabs that look like the dividers in a binder. Unselected tabs are sunk with ink-2 text. The selected tab takes the page fill, joins the panel below, and carries a 3px blue bar across its top. In the app bar the tabs sit on binder-tab and the current page tab takes the page fill. Counts use tabular numerals; in the app bar the count sits in a small blue box. Tab strips that scroll sideways fade the hidden edge over 2rem.

### Inline disclosures
Every secondary task opens in place. The approve, request information, and refer actions open the sign-off form below the buttons (180 ms rise). The policy viewer opens under "View policy". Engine settings open under each engine row: the connection boxes, then the fields for that connection, then model and reasoning effort. Fields sit in a two-column grid, and each text field takes one column. Keys are write-only password fields. Engine-call details use native disclosure rows. Each trigger carries its expanded state.

### Notices and designed absence
A notice is a 1px ruled box with an icon and text. The flag notice takes an orange border on flag wash. The action notice takes the blue wash. An absence is a dashed box on the page fill that names what is missing and offers the next action.

### Toasts
Bottom-right, up to 26rem wide. A binder-dark box with light text, a light-blue icon, and a close button. Error toasts use flag wash with an orange border and ink text. They rise 6px over 200 ms.

### Skeleton rows
Before marks arrive, the grid shows blank ruled rows: gray skeleton bars in the criterion column and dashed empty slots in the Verdict column. The bars sweep slowly (1.6 s) from sunk to rule.

### Inputs
White fields with a field-border outline and 2px corners. Hover darkens the outline to ink-2. Focus turns the outline blue with a 2px blue-wash halo. Invalid fields take an orange border and a deep-flag error line. Read-only and disabled fields take the sunk fill.

## Do's and Don'ts

### Do:
- **Do** put every secondary task in an inline disclosure next to its trigger.
- **Do** keep motion between 120 and 200 ms (the standard tint is 140 ms on the ease-out curve) and honor prefers-reduced-motion with instant swaps.
- **Do** keep the SLA countdown in the "Decision due" box of every case banner. Under four hours it turns deep flag. Overdue reads "Overdue" in 800 weight with a warning icon.
- **Do** offer only Approve, Request information, and Refer to MD as reviewer actions. Possible denials go to an MD.
- **Do** show a letter as read-only once it is marked ready.
- **Do** show "Demo — synthetic data, no PHI" in the app bar.
- **Do** mark selection with blue fills, rings, the tab top bar, and the 2px blue bottom underline on lit column headers and the next lifecycle stamp.

### Don't:
- **Don't** use modals, dialogs, or side panels.
- **Don't** add a deny button, a deny state, or any automated deny path.
- **Don't** stack a small label above a heading. Captions label values inside boxes.
- **Don't** use gradient text.
- **Don't** use colored side borders wider than 1px or inset side stripes on boxes, rows, notices, or quotes.
- **Don't** use offset or hard block shadows. The toast lift is the only shadow.
- **Don't** use pill shapes or card treatments. Corners stay at 2px (3px on tab tops) and regions are ruled, not lifted.
- **Don't** color a normal value, or add a success green.
- **Don't** name any vendor, guideline publisher, or product family. The product is "Prior Auth Express", and policies are public CMS NCDs and LCDs.

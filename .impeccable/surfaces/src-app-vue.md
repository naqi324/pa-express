---
version: 1
slug: "src-app-vue"
primary_target: "src/App.vue"
related_targets: ["src/components","src/styles"]
---

## Scope

The whole Prior Auth Express reviewer app (`src/`): Worklist, New request, Case workspace, Letter and audit, Engine settings. Visitor mode: Operate. A UM nurse works a daily desktop queue. Task: reach a defensible approve / request-information / refer decision per case, fast, with every criterion traced to verbatim record text.

## Direction contract

THESIS: The case is a clinical flowsheet. Policy criteria run down the rows, record documents run across the columns, and each cell charts where the evidence lives. It refuses the SaaS dashboard: KPI tiles, card stacks, and pill soup.

OWN-WORLD: White chart stock (#fbfcfd), blue-black charting ink (#1a2530), ruled grid gray (#d5dbe1), charted blue (#2f6f9f) for action and selection, and flag orange (#c2410c) only for exceptions. Normal values stay in ink; only abnormal gets color. Boxed form fields have small caption labels. Chart-divider tabs, group header rows, a code legend, and a sign-off strip. One legible workhorse sans with tabular figures.

STORY: The nurse scans the census-style worklist by remaining time, opens a case, reads the banner, and arrows through the grid. Each cell shows the quote highlighted in its document. They decide in the sign-off column.

FIRST VIEWPORT: Chart tabs sit on top. Below them, a boxed-field patient banner holds the SLA time right-aligned. Under the banner, a fixed lifecycle row of timestamp cells. Then the criteria × documents grid (about 9/12) beside a sticky decision column (about 3/12). The legend and sign-off strip sit at the bottom. The primary action is in the decision column.

FORM: Clinical Flowsheet. It was #1 on my ordered list and was chosen as the pick over roll #3. Seed key e1823080. Kept disciplines: running time, fixed stations, designed absence, read and write in one place, achromatic text, and linked selection. Signature interaction: crosshair keyboard grid. Selecting a cell lights its row and column headers, the quote in the document, and the cited letter line. Motion grammar: 120–200 ms state tints. When evaluation completes, marks are charted into the blank printed grid with a capped stagger. Instant swaps under reduced motion.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- Exact face: pick a legible workhorse sans with tabular figures, installed locally (no CDN).

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { ExternalLink, FileText, Flag, LoaderCircle } from '@lucide/vue';
import { docTypeLabel, markedParts } from '../documentText';
import { formatDate, policyId, policyLabel, verdictLabel } from '../format';
import { loadPolicy } from '../policies';
import type {
  ClinicalDocument,
  CriterionEvaluation,
  Determination,
  EvidenceCitation,
  PARequest,
  ReviewCriterion,
} from '../types';
import EvidenceQuote from './EvidenceQuote.vue';
import StatusChip from './StatusChip.vue';

// Criteria rows against submitted-document columns. Arrow keys move one cell;
// the selected cell lights its row and column headers, shows the criterion in
// the detail pane, and opens the cited document with the quote marked.
const props = defineProps<{
  request: PARequest;
  determination: Determination | null;
  analyzing: boolean;
}>();

const emit = defineEmits<{
  'show-document': [docId: string, quotes: string[]];
  'show-policy': [];
}>();

interface GridRow {
  id: string;
  text: string;
  depth: number;
  logic: string | null;
  evaluation: CriterionEvaluation | null;
}

interface Cell {
  row: number;
  col: number;
}

// Column 0 is the verdict; columns 1..n are the submitted documents.
const STATUS_COL = 0;

const PLACEHOLDER_ROWS = 5;

const STAGGER_MS = 45;

const STAGGER_CAP_MS = 540;

const gridRoot = ref<HTMLElement | null>(null);

const documentPane = ref<HTMLElement | null>(null);

const active = ref<Cell>({ row: 0, col: STATUS_COL });

const blankCriteria = ref<ReviewCriterion[]>([]);

const sawAnalyzing = ref(false);

const drawIn = ref(false);

const documents = computed(() => props.request.clinical_documents);

const evaluations = computed(() => props.determination?.criteria_evaluations ?? []);

const rows = computed<GridRow[]>(() => {
  if (props.determination) {
    return evaluations.value.map((evaluation) => ({
      id: evaluation.criterion_id,
      text: evaluation.criterion_text,
      depth: evaluation.depth,
      logic: evaluation.logic,
      evaluation,
    }));
  }

  return blankCriteria.value.map((criterion) => ({
    id: criterion.criterion_id,
    text: criterion.criterion_text,
    depth: criterion.depth,
    logic: criterion.logic,
    evaluation: null,
  }));
});

const interactive = computed(() => props.determination !== null && rows.value.length > 0);

const colCount = computed(() => documents.value.length + 1);

function citationsFor(row: GridRow, doc: ClinicalDocument): EvidenceCitation[] {
  return row.evaluation?.evidence.filter((citation) => citation.source_document === doc.title) ?? [];
}

// evidence[row][docIndex] — the quotes each criterion draws from each document.
const evidence = computed(() => rows.value.map((row) => documents.value.map((doc) => citationsFor(row, doc))));

function citedDocCol(row: number): number {
  const index = evidence.value[row]?.findIndex((quotes) => quotes.length > 0) ?? -1;

  return index === -1 ? STATUS_COL : index + 1;
}

function isException(row: GridRow): boolean {
  return row.evaluation !== null && row.evaluation.status !== 'MET';
}

// Open on the first exception, since that is what a reviewer checks first.
function initialCell(): Cell {
  const firstException = evaluations.value.findIndex((evaluation) => evaluation.status !== 'MET');
  const row = Math.max(firstException, 0);

  return { row, col: citedDocCol(row) };
}

const activeRow = computed(() => rows.value[active.value.row] ?? null);

const activeEvaluation = computed(() => activeRow.value?.evaluation ?? null);

// The document shown in the pane: the selected column, or for the verdict
// column the first document the criterion cites.
const activeDocIndex = computed(() => {
  if (active.value.col !== STATUS_COL) return active.value.col - 1;

  const cited = citedDocCol(active.value.row);

  return cited === STATUS_COL ? -1 : cited - 1;
});

const activeDocument = computed(() => documents.value[activeDocIndex.value] ?? null);

const activeQuotes = computed(() => {
  const quotes = evidence.value[active.value.row]?.[activeDocIndex.value] ?? [];

  return quotes.map((citation) => citation.quote);
});

const documentParts = computed(() =>
  activeDocument.value ? markedParts(activeDocument.value.text, activeQuotes.value) : [],
);

const quoteMissing = computed(
  () => activeQuotes.value.length > 0 && !documentParts.value.some((part) => part.mark),
);

// One short line for screen readers after each move; the detail pane itself
// stays silent so a reviewer is not read a full rationale per keystroke.
const selectionStatus = computed(() => {
  const evaluation = activeEvaluation.value;

  if (!evaluation) return '';

  const source = activeDocument.value ? activeDocument.value.title : 'No cited document';

  return `Row ${active.value.row + 1} of ${rows.value.length}, ${verdictLabel(evaluation.status)}. ${source}.`;
});

const evidenceCoverage = computed(() => {
  if (!props.determination) return null;

  const citedTitles = new Set(
    evaluations.value.flatMap((evaluation) => evaluation.evidence.map((citation) => citation.source_document)),
  );

  const cited: ClinicalDocument[] = [];
  const uncited: ClinicalDocument[] = [];

  for (const doc of documents.value) {
    if (citedTitles.has(doc.title)) cited.push(doc);
    else uncited.push(doc);
  }

  return { cited, uncited, total: documents.value.length };
});

const cmsLinkLabel = computed(() => {
  const policy = props.request.policy;

  if (!policy) return '';

  return policy.source_type === 'ncd'
    ? `Open NCD ${policy.ncd_id ?? policy.code} on cms.gov`
    : `Open LCD ${policy.lcd_id ?? policy.code} on cms.gov`;
});

function isActive(row: number, col: number): boolean {
  return active.value.row === row && active.value.col === col;
}

function cellId(row: number, col: number): string {
  return `cell-${props.request.id}-${row}-${col}`;
}

function markDelay(row: number): string {
  return `${Math.min(row * STAGGER_MS, STAGGER_CAP_MS)}ms`;
}

function quoteCount(count: number, doc: ClinicalDocument): string {
  if (count === 0) return `Not cited in ${doc.title}`;

  return `${count} quote${count === 1 ? '' : 's'} from ${doc.title}`;
}

function focusCell(cell: Cell): void {
  active.value = cell;
  void nextTick(() => {
    gridRoot.value?.querySelector<HTMLElement>(`[data-cell="${cell.row}-${cell.col}"]`)?.focus();
  });
}

function select(row: number, col: number): void {
  if (!interactive.value) return;

  focusCell({ row, col });
}

function clamp(value: number, max: number): number {
  return Math.min(Math.max(value, 0), max);
}

function onKeydown(event: KeyboardEvent): void {
  if (!interactive.value) return;

  const lastRow = rows.value.length - 1;
  const lastCol = colCount.value - 1;
  const { row, col } = active.value;
  let next: Cell | null = null;

  if (event.key === 'ArrowDown') next = { row: clamp(row + 1, lastRow), col };
  else if (event.key === 'ArrowUp') next = { row: clamp(row - 1, lastRow), col };
  else if (event.key === 'ArrowRight') next = { row, col: clamp(col + 1, lastCol) };
  else if (event.key === 'ArrowLeft') next = { row, col: clamp(col - 1, lastCol) };
  else if (event.key === 'Home') next = event.ctrlKey ? { row: 0, col: STATUS_COL } : { row, col: STATUS_COL };
  else if (event.key === 'End') next = event.ctrlKey ? { row: lastRow, col: lastCol } : { row, col: lastCol };
  else if (event.key === 'PageDown') next = { row: lastRow, col };
  else if (event.key === 'PageUp') next = { row: 0, col };

  if (!next) return;

  event.preventDefault();
  focusCell(next);
}

// Pick a quote in the detail pane: move the grid to that document's cell.
function openCitation(citation: EvidenceCitation): void {
  const index = documents.value.findIndex((doc) => doc.title === citation.source_document);

  if (index !== -1) select(active.value.row, index + 1);
}

function isOpenCitation(citation: EvidenceCitation): boolean {
  return activeDocument.value?.title === citation.source_document;
}

// Keep the first marked passage in view inside the document pane only, so
// the page itself does not jump while the reviewer moves through the grid.
function revealMark(): void {
  const pane = documentPane.value;
  const mark = pane?.querySelector('mark');

  if (!pane || !mark) return;

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const top = mark.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - 48;

  pane.scrollTo({ top: Math.max(top, 0), behavior: reduced ? 'auto' : 'smooth' });
}

async function loadBlankCriteria(): Promise<void> {
  const { policy, scenario_id: scenarioId } = props.request;

  blankCriteria.value = [];

  if (!policy) return;

  const document = await loadPolicy(policyId(policy));
  const set = document?.review_criteria.find((entry) => entry.scenario_id === scenarioId);

  if (props.determination === null) blankCriteria.value = set?.criteria ?? [];
}

watch(
  () => [props.request.id, props.analyzing],
  () => {
    if (props.analyzing) {
      sawAnalyzing.value = true;

      if (!props.determination) void loadBlankCriteria();
    }
  },
  { immediate: true },
);

watch(
  () => props.request.id,
  () => {
    sawAnalyzing.value = props.analyzing;
    drawIn.value = false;
  },
);

watch(
  () => props.determination?.id,
  (id) => {
    if (!id) return;

    drawIn.value = sawAnalyzing.value;
    active.value = initialCell();
  },
  { immediate: true },
);

watch([activeDocument, activeQuotes], () => {
  void nextTick(revealMark);
});
</script>

<template>
  <section class="criteria" aria-labelledby="criteria-title">
    <header class="criteria-head">
      <div class="criteria-head-text">
        <h2 id="criteria-title" class="criteria-title">Criterion-by-criterion evaluation</h2>
        <p class="criteria-context">
          Evaluated against {{ policyLabel(request.policy) }}
        </p>
      </div>
      <div class="criteria-links">
        <button v-if="request.policy" type="button" class="btn btn-quiet btn-small" @click="emit('show-policy')">
          <FileText :size="14" aria-hidden="true" />
          View policy
        </button>
        <a
          v-if="request.policy?.source_url"
          class="btn btn-quiet btn-small"
          :href="request.policy.source_url"
          target="_blank"
          rel="noopener noreferrer"
        >
          <ExternalLink :size="14" aria-hidden="true" />
          {{ cmsLinkLabel }}
        </a>
      </div>
    </header>

    <p v-if="analyzing && !determination" class="analysis-status" role="status">
      <LoaderCircle :size="16" class="spin" aria-hidden="true" />
      Analyzing clinical documentation against {{ request.policy?.code ?? 'policy' }} criteria…
    </p>

    <div v-if="!determination && !analyzing" class="absence">
      <h3>No evaluation yet</h3>
      <p>
        Criterion-by-criterion results appear here when the analysis completes — each criterion gets a Met / Not met /
        Insufficient verdict with verbatim evidence quotes naming their source document.
      </p>
    </div>

    <template v-else>
      <div class="grid-frame">
        <div
          ref="gridRoot"
          role="grid"
          class="criteria-grid"
          :class="{ 'is-blank': !determination, 'is-drawing': drawIn }"
          :style="{ '--doc-cols': documents.length }"
          :aria-busy="!determination"
          :aria-rowcount="rows.length + 1"
          :aria-colcount="colCount + 1"
          aria-labelledby="criteria-title"
          :aria-describedby="interactive ? 'grid-help' : undefined"
          @keydown="onKeydown"
        >
          <div role="row" class="grid-row grid-head" aria-rowindex="1">
            <div role="columnheader" class="grid-corner" aria-colindex="1">Criterion</div>
            <div
              role="columnheader"
              class="col-head col-head-status"
              :class="{ 'is-lit': interactive && active.col === 0 }"
              aria-colindex="2"
            >
              Verdict
            </div>
            <div
              v-for="(doc, index) in documents"
              :key="doc.id"
              role="columnheader"
              class="col-head"
              :class="{ 'is-lit': interactive && active.col === index + 1 }"
              :aria-colindex="index + 3"
              :title="doc.title"
            >
              <span class="col-head-type">{{ docTypeLabel(doc.doc_type) }}</span>
              <span class="col-head-date num">{{ formatDate(doc.date) }}</span>
              <span class="visually-hidden">{{ doc.title }}</span>
            </div>
          </div>

          <template v-if="rows.length > 0">
            <div
              v-for="(row, rowIndex) in rows"
              :key="row.id"
              role="row"
              class="grid-row"
              :class="{ 'is-lit': interactive && active.row === rowIndex, 'is-exception': isException(row) }"
              :aria-rowindex="rowIndex + 2"
            >
              <div
                role="rowheader"
                class="row-head"
                :style="{ '--depth': Math.max(row.depth, 0) }"
                aria-colindex="1"
                @click="select(rowIndex, active.col)"
              >
                <span class="row-text"><Flag v-if="isException(row)" :size="12" :stroke-width="2.5" class="row-flag" aria-hidden="true" />{{ row.text }}</span>
                <span v-if="row.logic" class="row-logic">{{ row.logic }}</span>
              </div>
              <div
                role="gridcell"
                class="cell cell-status"
                :class="{ 'is-active': interactive && isActive(rowIndex, 0), 'in-col': interactive && active.col === 0 }"
                :data-cell="`${rowIndex}-0`"
                :id="cellId(rowIndex, 0)"
                :tabindex="interactive && isActive(rowIndex, 0) ? 0 : -1"
                :aria-selected="interactive ? isActive(rowIndex, 0) : undefined"
                aria-colindex="2"
                @click="select(rowIndex, 0)"
              >
                <StatusChip
                  v-if="row.evaluation"
                  :value="row.evaluation.status"
                  class="ink-mark"
                  :style="{ '--delay': markDelay(rowIndex) }"
                />
                <span v-else class="status-slot" aria-hidden="true" />
              </div>
              <div
                v-for="(doc, docIndex) in documents"
                :key="doc.id"
                role="gridcell"
                class="cell cell-doc"
                :class="{
                  'is-active': interactive && isActive(rowIndex, docIndex + 1),
                  'in-col': interactive && active.col === docIndex + 1,
                }"
                :data-cell="`${rowIndex}-${docIndex + 1}`"
                :tabindex="interactive && isActive(rowIndex, docIndex + 1) ? 0 : -1"
                :aria-selected="interactive ? isActive(rowIndex, docIndex + 1) : undefined"
                :aria-colindex="docIndex + 3"
                @click="select(rowIndex, docIndex + 1)"
              >
                <template v-if="row.evaluation">
                  <span
                    v-if="(evidence[rowIndex]?.[docIndex]?.length ?? 0) > 0"
                    class="evidence-mark ink-mark num"
                    :style="{ '--delay': markDelay(rowIndex) }"
                    aria-hidden="true"
                  >
                    <span class="evidence-dot" :class="{ 'is-gap': isException(row) }" />
                    <template v-if="(evidence[rowIndex]?.[docIndex]?.length ?? 0) > 1">{{ evidence[rowIndex]?.[docIndex]?.length }}</template>
                  </span>
                  <span class="visually-hidden">{{ quoteCount(evidence[rowIndex]?.[docIndex]?.length ?? 0, doc) }}</span>
                </template>
              </div>
            </div>
          </template>
          <template v-else>
            <div
              v-for="placeholder in PLACEHOLDER_ROWS"
              :key="placeholder"
              role="row"
              class="grid-row"
              :aria-rowindex="placeholder + 1"
            >
              <div role="rowheader" class="row-head" aria-colindex="1">
                <span class="skeleton-bar" :style="{ width: `${50 + ((placeholder * 17) % 40)}%` }" />
              </div>
              <div role="gridcell" class="cell cell-status" aria-colindex="2">
                <span class="status-slot" aria-hidden="true" />
              </div>
              <div
                v-for="(doc, docIndex) in documents"
                :key="doc.id"
                role="gridcell"
                class="cell cell-doc"
                :aria-colindex="docIndex + 3"
              />
            </div>
          </template>
        </div>
      </div>

      <div v-if="determination" class="legend caption" role="group" aria-label="Grid legend">
        <span class="legend-item"><StatusChip value="MET" /> Criterion met</span>
        <span class="legend-item"><StatusChip value="NOT_MET" /> Not met</span>
        <span class="legend-item"><StatusChip value="INSUFFICIENT" /> Not enough documentation</span>
        <span class="legend-item"><Flag :size="12" :stroke-width="2.5" class="row-flag" aria-hidden="true" /> Needs attention</span>
        <span class="legend-item"><span class="evidence-dot" aria-hidden="true" /> Quoted as evidence (count if more than one)</span>
        <span class="legend-item"><span class="evidence-dot is-gap" aria-hidden="true" /> Quoted, but short of the criterion</span>
        <span class="legend-item"><span class="legend-blank" aria-hidden="true" /> Not cited</span>
        <span v-if="interactive" id="grid-help" class="legend-help">Arrow keys move between cells. Home and End jump to the ends of a row.</span>
      </div>

      <div v-if="determination && activeRow" class="inspect">
        <p class="visually-hidden" role="status">{{ selectionStatus }}</p>
        <section class="detail" aria-labelledby="detail-title">
          <div class="detail-head">
            <h3 id="detail-title" class="detail-title">{{ activeRow.text }}</h3>
            <span v-if="activeRow.logic" class="row-logic">{{ activeRow.logic }}</span>
          </div>
          <div v-if="activeEvaluation" class="detail-verdict">
            <StatusChip :value="activeEvaluation.status" />
            <span class="caption num">Confidence: {{ activeEvaluation.confidence }}%</span>
          </div>
          <p v-if="activeEvaluation" class="detail-rationale">{{ activeEvaluation.rationale }}</p>
          <div v-if="activeEvaluation && activeEvaluation.evidence.length > 0" class="detail-quotes">
            <EvidenceQuote
              v-for="(citation, index) in activeEvaluation.evidence"
              :key="index"
              :citation="citation"
              :active="isOpenCitation(citation)"
              :flagged="activeEvaluation.status !== 'MET'"
              @open="openCitation(citation)"
            />
          </div>
          <p v-else class="detail-none">No supporting documentation found.</p>
        </section>

        <section class="document" aria-labelledby="document-title">
          <template v-if="activeDocument">
            <header class="document-head">
              <h3 id="document-title" class="document-title">{{ activeDocument.title }}</h3>
              <span class="caption">{{ docTypeLabel(activeDocument.doc_type) }} · <span class="num">{{ formatDate(activeDocument.date) }}</span></span>
              <button type="button" class="btn btn-quiet btn-small" @click="emit('show-document', activeDocument.id, activeQuotes)">
                Open in submission
              </button>
            </header>
            <p v-if="activeQuotes.length === 0" class="document-note caption">This document is not cited for the selected criterion.</p>
            <p v-else-if="quoteMissing" class="document-note caption">The quoted passage was not found verbatim in this document.</p>
            <div ref="documentPane" class="document-text" :class="{ 'is-gap': activeEvaluation && activeEvaluation.status !== 'MET' }" tabindex="0" :aria-label="`${activeDocument.title}, full text`">
              <template v-for="(part, index) in documentParts" :key="index"><mark v-if="part.mark">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template>
            </div>
          </template>
          <div v-else class="absence document-absence">
            <h3 id="document-title">No supporting text in the record</h3>
            <p>None of the submitted documents is quoted for this criterion.</p>
          </div>
        </section>
      </div>

      <div v-if="evidenceCoverage" class="sources">
        <p class="sources-title num">
          {{
            evidenceCoverage.cited.length > 0
              ? `Evidence sources — ${evidenceCoverage.cited.length} of ${evidenceCoverage.total} attached documents cited`
              : 'Evidence sources — no attached documents cited'
          }}
        </p>
        <dl class="facts">
          <dt>Cited</dt>
          <dd v-if="evidenceCoverage.cited.length > 0" class="sources-cited">
            <button
              v-for="doc in evidenceCoverage.cited"
              :key="doc.id"
              type="button"
              class="link-button"
              @click="emit('show-document', doc.id, [])"
            >
              {{ doc.title }}
            </button>
          </dd>
          <dd v-else>—</dd>
          <dt>Not cited</dt>
          <dd>{{ evidenceCoverage.uncited.length > 0 ? evidenceCoverage.uncited.map((doc) => doc.title).join(' · ') : '—' }}</dd>
        </dl>
      </div>
    </template>
  </section>
</template>

<style scoped>
.criteria {
  display: grid;
  gap: var(--space-4);
}

.criteria-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3) var(--space-5);
}

.criteria-head-text {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
}

.criteria-title {
  font-size: var(--text-h3);
}

.criteria-context {
  color: var(--ink-2);
  font-size: var(--text-small);
}

.criteria-links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-right: -0.5rem;
}

.analysis-status {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  color: var(--ink-2);
  font-weight: 600;
}

.analysis-status svg {
  color: var(--action);
}

.grid-frame {
  position: relative;
  max-block-size: min(26rem, 50vh);
  overflow: auto;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
}

.criteria-grid {
  --criterion-min: 18rem;
  --status-col: 8.5rem;
  --doc-col: 7.25rem;

  display: grid;
  grid-template-columns: minmax(var(--criterion-min), 1fr) var(--status-col) repeat(var(--doc-cols), var(--doc-col));
  min-width: calc(var(--criterion-min) + var(--status-col) + var(--doc-cols) * var(--doc-col));
  font-variant-numeric: tabular-nums;
}

.criteria-grid:focus-within {
  outline: none;
}

.grid-row {
  display: contents;
}

.grid-head > * {
  position: sticky;
  top: 0;
  z-index: 2;
  display: grid;
  align-content: end;
  gap: 0.0625rem;
  padding: 0.5rem 0.625rem;
  border-bottom: 1px solid var(--rule-strong);
  background: var(--sunk);
  color: var(--ink-2);
  font-size: var(--text-caption);
  font-weight: 700;
  line-height: 1.25;
  transition:
    background-color var(--tint),
    color var(--tint);
}

.grid-corner {
  left: 0;
  z-index: 3;
}

.col-head {
  border-left: 1px solid var(--rule);
  text-align: center;
  justify-items: center;
}

.col-head-date {
  color: var(--ink-3);
  font-weight: 600;
}

.col-head.is-lit {
  background: var(--action-wash-2);
  color: var(--ink);
  box-shadow: inset 0 -2px 0 var(--action);
}

.col-head.is-lit .col-head-date {
  color: var(--ink-2);
}

.row-head,
.cell {
  border-bottom: 1px solid var(--rule);
  transition: background-color var(--tint);
}

.row-head {
  position: sticky;
  left: 0;
  z-index: 1;
  display: grid;
  gap: 0.125rem;
  align-content: center;
  padding: 0.5rem 0.75rem 0.5rem calc(0.75rem + var(--depth, 0) * 1.125rem);
  background: var(--paper);
  font-size: var(--text-small);
  line-height: 1.4;
  cursor: default;
}

.grid-row:last-child > * {
  border-bottom: 0;
}

.row-logic {
  color: var(--ink-3);
  font-size: var(--text-caption);
  font-weight: 700;
}

.grid-row.is-exception .row-text {
  font-weight: 600;
}

.row-flag {
  color: var(--flag);
}

.row-text .row-flag {
  margin-right: 0.3125rem;
  vertical-align: -0.0625rem;
}

.grid-row.is-lit .row-head {
  background: var(--action-wash-2);
}

.cell {
  display: grid;
  place-items: center;
  min-height: 2.75rem;
  padding: 0.375rem;
  border-left: 1px solid var(--rule);
  cursor: pointer;
}

.is-blank .cell {
  cursor: default;
}

.cell-status {
  justify-items: start;
  padding-left: 0.625rem;
}

.grid-row.is-lit .cell,
.cell.in-col {
  background: var(--action-wash);
}

.cell.is-active {
  background: var(--action-wash-2);
  box-shadow: inset 0 0 0 2px var(--action);
}

.cell:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px var(--action), inset 0 0 0 4px var(--paper);
}

.cell:hover:not(.is-active) {
  background: var(--action-wash);
}

.is-blank .cell:hover {
  background: transparent;
}

.status-slot {
  display: block;
  width: 5rem;
  height: 1.375rem;
  border: 1px dashed var(--rule-strong);
  border-radius: var(--radius);
}

.evidence-mark {
  display: inline-flex;
  gap: 0.25rem;
  align-items: center;
  font-size: var(--text-caption);
  font-weight: 700;
}

.evidence-dot {
  display: inline-block;
  width: 0.625rem;
  height: 0.625rem;
  border-radius: 1px;
  background: var(--ink);
}

.evidence-dot.is-gap {
  border: 2px solid var(--flag);
  border-radius: 50%;
  background: transparent;
}

.is-drawing .ink-mark {
  animation: ink-in 200ms var(--ease-out) both;
  animation-delay: var(--delay, 0ms);
}

@keyframes ink-in {
  from {
    opacity: 0;
    transform: scale(0.6);
  }
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  align-items: center;
}

.legend-item {
  display: inline-flex;
  gap: 0.375rem;
  align-items: center;
}

.legend-blank {
  display: inline-block;
  width: 1rem;
  height: 1rem;
  border: 1px solid var(--rule);
  background: var(--paper);
}

.legend-help {
  margin-left: auto;
  color: var(--ink-3);
}

.inspect {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
}

.detail {
  display: grid;
  align-content: start;
  gap: var(--space-3);
  padding: var(--space-4);
  border-right: 1px solid var(--rule);
}

.detail-head {
  display: grid;
  gap: 0.125rem;
}

.detail-title {
  font-size: var(--text-body);
  line-height: 1.4;
}

.detail-verdict {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}

.detail-rationale {
  color: var(--ink-2);
  font-size: var(--text-small);
}

.detail-quotes {
  display: grid;
  gap: var(--space-2);
}

.detail-none {
  color: var(--flag-deep);
  font-size: var(--text-small);
  font-weight: 600;
}

.document {
  display: grid;
  grid-template-rows: auto auto 1fr;
  min-width: 0;
}

.document-head {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0 var(--space-3);
  align-items: end;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--rule);
  background: var(--surface);
}

.document-head .caption {
  grid-column: 1;
}

.document-title {
  grid-column: 1;
  font-size: var(--text-body);
}

.document-head .btn {
  grid-column: 2;
  grid-row: 1 / span 2;
}

.document-note {
  padding: var(--space-2) var(--space-4) 0;
}

.document-text {
  max-height: 18rem;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4) var(--space-4);
  font-size: var(--text-small);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.document-text.is-gap mark {
  background: var(--flag-wash);
  box-shadow: 0 0 0 2px var(--flag-wash);
  border-bottom-color: var(--flag);
}

.document-absence {
  margin: var(--space-4);
}

.sources {
  display: grid;
  gap: var(--space-2);
}

.sources-title {
  font-weight: 700;
}

.sources-cited {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem var(--space-3);
}

.link-button {
  padding: 0;
  border: 0;
  background: none;
  color: var(--action-deep);
  text-align: left;
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 0.2em;
  cursor: pointer;
}

.link-button:hover {
  color: var(--ink);
}

@media (max-width: 60rem) {
  .inspect {
    grid-template-columns: 1fr;
  }

  .detail {
    border-right: 0;
    border-bottom: 1px solid var(--rule);
  }
}

@media (max-width: 48rem) {
  .grid-frame {
    max-block-size: none;
  }
}

@media (max-width: 40rem) {
  .criteria-grid {
    --criterion-min: 12rem;
    --status-col: 7.5rem;
    --doc-col: 6rem;
  }
}
</style>

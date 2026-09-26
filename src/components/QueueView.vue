<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ChevronLeft, ChevronRight, Inbox, LoaderCircle, Plus } from '@lucide/vue';
import { planTypeLabel } from '../format';
import { useAppStore } from '../store';
import { notify } from '../toast';
import type { PARequestSummary, Urgency } from '../types';
import CaseStatusChip from './CaseStatusChip.vue';
import RecommendationIndicator from './RecommendationIndicator.vue';
import SlaCountdown from './SlaCountdown.vue';

type QueueFilter = 'all' | 'review' | 'disposed';

interface UrgencyGroup {
  urgency: Urgency;
  label: string;
  rows: PARequestSummary[];
}

const store = useAppStore();

const { state } = store;

const PAGE_SIZE = 15;

const QUEUE_POLL_MS = 4000;

const FILTERS: { id: QueueFilter; label: string }[] = [
  { id: 'all', label: 'All cases' },
  { id: 'review', label: 'Needs my review' },
  { id: 'disposed', label: 'Disposed' },
];

const GROUP_LABELS: Record<Urgency, string> = {
  expedited: 'Expedited — 72-hour decision',
  standard: 'Standard — 7-day decision',
};

const filter = ref<QueueFilter>('all');

const page = ref(0);

const seeding = ref(false);

// Expedited first. Within each group, open cases come before decided ones,
// then the earliest decision deadline.
function worklistCompare(left: PARequestSummary, right: PARequestSummary): number {
  if (left.urgency !== right.urgency) return left.urgency === 'expedited' ? -1 : 1;

  const leftOpen = left.determination_status === 'in_review';

  if (leftOpen !== (right.determination_status === 'in_review')) return leftOpen ? -1 : 1;

  return new Date(left.sla_due_at).getTime() - new Date(right.sla_due_at).getTime();
}

function matchesFilter(request: PARequestSummary): boolean {
  if (filter.value === 'review') return request.determination_status === 'in_review';

  if (filter.value === 'disposed') return request.determination_status !== 'in_review';

  return true;
}

const ordered = computed(() => state.requests.toSorted(worklistCompare));

const visible = computed(() => ordered.value.filter(matchesFilter));

const needsReview = computed(() => ordered.value.filter((request) => request.determination_status === 'in_review'));

const pageCount = computed(() => Math.max(1, Math.ceil(visible.value.length / PAGE_SIZE)));

const pageRows = computed(() => visible.value.slice(page.value * PAGE_SIZE, (page.value + 1) * PAGE_SIZE));

const groups = computed<UrgencyGroup[]>(() => {
  const result: UrgencyGroup[] = [];

  for (const urgency of ['expedited', 'standard'] as const) {
    const rows = pageRows.value.filter((request) => request.urgency === urgency);

    if (rows.length > 0) result.push({ urgency, label: GROUP_LABELS[urgency], rows });
  }

  return result;
});

const rangeLabel = computed(() => {
  const start = page.value * PAGE_SIZE + 1;
  const end = Math.min(visible.value.length, (page.value + 1) * PAGE_SIZE);

  return `Rows ${start}–${end} of ${visible.value.length}`;
});

const allSamplesLoaded = computed(() => {
  if (state.scenarios.length === 0) return false;

  const loaded = new Set(state.requests.map((request) => request.scenario_id));

  return state.scenarios.every((scenario) => loaded.has(scenario.id));
});

const showSkeleton = computed(() => state.loadingRequests && state.requests.length === 0);

const filterEmptyCopy = computed(() => {
  if (filter.value === 'review') return 'No cases need your review right now.';

  if (filter.value === 'disposed') return 'No cases have a disposition yet.';

  return 'No cases match this filter.';
});

watch(filter, () => {
  page.value = 0;
});

watch(pageCount, (count) => {
  if (page.value > count - 1) page.value = count - 1;
});

function reviewNext(): void {
  const next = needsReview.value[0];

  if (next) void store.openRequest(next.id);
}

async function loadSamples(): Promise<void> {
  seeding.value = true;

  const loaded = await store.seedRequests();

  seeding.value = false;

  if (loaded) notify('success', 'Sample caseload loaded. Each case is being analyzed now.');
}

function serviceCodes(request: PARequestSummary): string {
  return request.cpt_codes.map((code) => `CPT ${code}`).join(' · ');
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

function stopPolling(): void {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = null;
}

watch(
  store.hasActiveEvaluations,
  (active) => {
    if (active && !pollTimer) {
      pollTimer = setInterval(() => void store.pollRequestsOnce(), QUEUE_POLL_MS);
    } else if (!active) {
      stopPolling();
    }
  },
  { immediate: true },
);

onMounted(() => {
  void store.refreshRequests();

  if (state.scenarios.length === 0) void store.refreshScenarios();
});

onBeforeUnmount(stopPolling);
</script>

<template>
  <section class="page" aria-labelledby="worklist-title">
    <div class="page-head">
      <div class="page-head-text">
        <h1 id="worklist-title">Worklist</h1>
        <p class="muted num">
          <template v-if="needsReview.length > 0">{{ needsReview.length }} awaiting review</template>
          <template v-else>All caught up</template>
        </p>
      </div>
      <div class="page-head-actions">
        <button type="button" class="btn btn-primary" :disabled="needsReview.length === 0" @click="reviewNext">
          Review next case
          <ChevronRight :size="16" aria-hidden="true" />
        </button>
        <button
          v-if="!allSamplesLoaded && state.requests.length > 0"
          type="button"
          class="btn"
          :disabled="seeding"
          @click="loadSamples"
        >
          <LoaderCircle v-if="seeding" :size="15" class="spin" aria-hidden="true" />
          {{ seeding ? 'Loading sample caseload…' : 'Load sample caseload' }}
        </button>
        <button type="button" class="btn" @click="store.navigate('new-request')">
          <Plus :size="15" aria-hidden="true" />
          New request
        </button>
      </div>
    </div>

    <div v-if="showSkeleton" class="worklist-frame" aria-busy="true" aria-label="Loading worklist">
      <table class="ruled worklist">
        <thead>
          <tr>
            <th scope="col">Time to decision</th>
            <th scope="col">Request</th>
            <th scope="col">Member</th>
            <th scope="col">Service</th>
            <th scope="col">Plan</th>
            <th scope="col">Recommendation</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in 5" :key="row" class="skeleton-row">
            <td v-for="cell in 7" :key="cell"><span class="skeleton-bar" :style="{ width: `${40 + ((row * cell) % 5) * 12}%` }" /></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else-if="state.requests.length === 0" class="absence worklist-empty">
      <Inbox :size="22" aria-hidden="true" />
      <h2>Your worklist is clear</h2>
      <p>New prior auth requests appear here when they are ready for review.</p>
      <div class="absence-actions">
        <button type="button" class="btn btn-primary" :disabled="seeding" @click="loadSamples">
          <LoaderCircle v-if="seeding" :size="15" class="spin" aria-hidden="true" />
          {{ seeding ? 'Loading sample caseload…' : 'Load sample caseload' }}
        </button>
        <button type="button" class="btn" @click="store.navigate('new-request')">Create one request</button>
      </div>
    </div>

    <template v-else>
      <div class="worklist-tools">
        <div class="filter" role="radiogroup" aria-label="Filter cases">
          <button
            v-for="option in FILTERS"
            :key="option.id"
            type="button"
            role="radio"
            class="filter-option"
            :aria-checked="filter === option.id"
            @click="filter = option.id"
          >
            {{ option.label }}
          </button>
        </div>
        <p class="range num muted">{{ rangeLabel }}</p>
      </div>

      <div class="worklist-frame">
        <table class="ruled worklist worklist-live" role="table">
          <thead role="rowgroup">
            <tr role="row">
              <th scope="col" role="columnheader">Time to decision</th>
              <th scope="col" role="columnheader">Request</th>
              <th scope="col" role="columnheader">Member</th>
              <th scope="col" role="columnheader">Service</th>
              <th scope="col" role="columnheader">Plan</th>
              <th scope="col" role="columnheader">Recommendation</th>
              <th scope="col" role="columnheader">Status</th>
            </tr>
          </thead>
          <tbody v-for="group in groups" :key="group.urgency" role="rowgroup">
            <tr class="group-row" role="row">
              <th colspan="7" scope="colgroup" role="rowheader">
                {{ group.label }} <span class="group-count num">{{ group.rows.length }}</span>
              </th>
            </tr>
            <tr
              v-for="request in group.rows"
              :key="request.id"
              class="worklist-row"
              role="row"
              :class="{ 'row-disposed': request.determination_status !== 'in_review' }"
              @click="store.openRequest(request.id)"
            >
              <td class="cell-sla" role="cell">
                <SlaCountdown
                  v-if="request.determination_status === 'in_review'"
                  :due-at="request.sla_due_at"
                  :expedited="request.urgency === 'expedited'"
                />
                <span v-else class="muted">Decided</span>
              </td>
              <td class="cell-id" role="cell">
                <button type="button" class="request-id num" @click.stop="store.openRequest(request.id)">
                  {{ request.id }}
                </button>
              </td>
              <td class="cell-member" role="cell">{{ request.member_name }}</td>
              <td class="cell-service" role="cell">
                <span>{{ request.service_description }}</span>
                <span class="codes num">{{ serviceCodes(request) }}</span>
              </td>
              <td class="cell-plan" role="cell">{{ planTypeLabel(request.plan_type) }}</td>
              <td class="cell-rec" role="cell">
                <RecommendationIndicator :recommendation="request.recommendation" :processing="request.processing_status" />
              </td>
              <td class="cell-status" role="cell">
                <CaseStatusChip
                  :processing="request.processing_status"
                  :determination="request.determination_status"
                  :notified="request.notified_at !== null"
                />
              </td>
            </tr>
          </tbody>
          <tbody v-if="visible.length === 0" role="rowgroup">
            <tr role="row">
              <td colspan="7" class="filter-empty muted" role="cell">{{ filterEmptyCopy }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <nav v-if="pageCount > 1" class="pager" aria-label="Worklist pages">
        <button type="button" class="btn btn-small" :disabled="page === 0" @click="page -= 1">
          <ChevronLeft :size="14" aria-hidden="true" />
          Previous
        </button>
        <span class="num muted">Page {{ page + 1 }} of {{ pageCount }}</span>
        <button type="button" class="btn btn-small" :disabled="page >= pageCount - 1" @click="page += 1">
          Next
          <ChevronRight :size="14" aria-hidden="true" />
        </button>
      </nav>
    </template>
  </section>
</template>

<style scoped>
.worklist-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.filter {
  display: inline-flex;
  border: 1px solid var(--field-border);
  border-radius: var(--radius);
  background: var(--paper);
}

.filter-option {
  min-height: var(--control-height-small);
  padding: 0 0.75rem;
  border: 0;
  border-right: 1px solid var(--rule-strong);
  background: transparent;
  color: var(--ink-2);
  font-size: var(--text-small);
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color var(--tint),
    color var(--tint);
}

.filter-option:last-child {
  border-right: 0;
}

.filter-option:hover {
  background: var(--action-wash);
  color: var(--ink);
}

.filter-option[aria-checked='true'] {
  background: var(--ink);
  color: var(--paper);
}

.range {
  font-size: var(--text-small);
}

.worklist-frame {
  position: relative;
  overflow-x: auto;
  border-right: 1px solid var(--rule);
  border-left: 1px solid var(--rule);
}

.worklist {
  min-width: 60rem;
}

.worklist-row {
  cursor: pointer;
  transition: background-color var(--tint);
}

.worklist-row:hover {
  background: var(--action-wash);
}

.worklist-row:has(:focus-visible) {
  background: var(--action-wash);
}

.row-disposed .cell-member,
.row-disposed .cell-service,
.row-disposed .cell-plan {
  color: var(--ink-2);
}

.cell-sla {
  width: 9.5rem;
}

.request-id {
  padding: 0;
  border: 0;
  background: none;
  color: var(--action-deep);
  font-weight: 700;
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 0.2em;
  cursor: pointer;
}

.request-id:hover {
  color: var(--ink);
}

.cell-member {
  font-weight: 600;
  white-space: nowrap;
}

.cell-service {
  display: grid;
  gap: 0.125rem;
  min-width: 16rem;
}

.codes {
  color: var(--ink-3);
  font-size: var(--text-caption);
  font-weight: 600;
}

.cell-plan {
  white-space: nowrap;
}

.group-count {
  margin-left: 0.375rem;
  color: var(--ink-3);
}

.skeleton-row td {
  height: 2.875rem;
  vertical-align: middle;
}

.filter-empty {
  padding: var(--space-5) var(--space-4);
}

.worklist-empty {
  max-width: 40rem;
}

@media (max-width: 40rem) {
  .worklist {
    min-width: 0;
  }

  .worklist-live thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }

  .worklist-live .group-row,
  .worklist-live .group-row th {
    display: block;
  }

  .worklist-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      'id sla'
      'member plan'
      'service service'
      'rec status';
    gap: 0.25rem var(--space-3);
    padding: var(--space-3) 0.75rem;
    border-bottom: 1px solid var(--rule);
  }

  .worklist-row > td {
    padding: 0;
    border-bottom: 0;
  }

  .cell-sla {
    grid-area: sla;
    width: auto;
    justify-self: end;
  }

  .cell-id {
    grid-area: id;
  }

  .cell-member {
    grid-area: member;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .cell-plan {
    grid-area: plan;
    justify-self: end;
    color: var(--ink-2);
    font-size: var(--text-small);
  }

  .cell-service {
    grid-area: service;
    min-width: 0;
  }

  .cell-rec {
    grid-area: rec;
    align-self: center;
  }

  .cell-status {
    grid-area: status;
    justify-self: end;
  }
}

.pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-3);
  font-size: var(--text-small);
}
</style>

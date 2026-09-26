<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { ArrowLeft, ChevronRight, LoaderCircle } from '@lucide/vue';
import { planTypeLabel } from '../format';
import { useAppStore } from '../store';
import type { Urgency } from '../types';

const store = useAppStore();

const { state } = store;

const selectedId = ref<string | null>(null);

const urgency = ref<Urgency>('standard');

const submitting = ref(false);

const confirmHeading = ref<HTMLHeadingElement | null>(null);

const selected = computed(() => state.scenarios.find((scenario) => scenario.id === selectedId.value) ?? null);

const loading = computed(() => state.scenarios.length === 0);

async function choose(id: string): Promise<void> {
  selectedId.value = id;
  urgency.value = 'standard';
  await nextTick();
  confirmHeading.value?.focus();
}

function cancel(): void {
  selectedId.value = null;
}

async function submit(): Promise<void> {
  if (!selected.value) return;

  submitting.value = true;
  await store.createRequest(selected.value.id, urgency.value);
  submitting.value = false;
}

onMounted(() => {
  if (state.scenarios.length === 0) void store.refreshScenarios();
});
</script>

<template>
  <section class="page" aria-labelledby="new-request-title">
    <div class="page-head">
      <div class="page-head-text">
        <h1 id="new-request-title">New request</h1>
        <p class="muted">Choose a clinical scenario to submit as a prior authorization request. Analysis starts at intake.</p>
      </div>
      <div class="page-head-actions">
        <button type="button" class="btn" @click="store.navigate('queue')">
          <ArrowLeft :size="15" aria-hidden="true" />
          Back to worklist
        </button>
      </div>
    </div>

    <div class="intake">
      <div class="scenario-list" :aria-busy="loading">
        <h2 class="section-title">Scenarios</h2>
        <ul v-if="loading" class="scenarios" aria-label="Loading scenarios">
          <li v-for="row in 3" :key="row" class="scenario-skeleton">
            <span class="skeleton-bar" style="width: 55%" />
            <span class="skeleton-bar" style="width: 80%" />
            <span class="skeleton-bar" style="width: 40%" />
          </li>
        </ul>
        <ul v-else class="scenarios">
          <li v-for="scenario in state.scenarios" :key="scenario.id">
            <button
              type="button"
              class="scenario"
              :aria-pressed="selectedId === scenario.id"
              @click="choose(scenario.id)"
            >
              <span class="scenario-text">
                <span class="scenario-title">{{ scenario.title }}</span>
                <span class="scenario-subtitle">{{ scenario.subtitle }}</span>
                <span class="scenario-meta num">{{ scenario.policy_label }} · {{ planTypeLabel(scenario.plan_type) }}</span>
              </span>
              <ChevronRight :size="16" aria-hidden="true" />
            </button>
          </li>
        </ul>
      </div>

      <aside class="confirm" aria-live="polite">
        <form v-if="selected" class="confirm-form" @submit.prevent="submit">
          <h2 ref="confirmHeading" tabindex="-1" class="confirm-title">{{ selected.title }}</h2>
          <div class="boxes confirm-boxes">
            <div class="box box-full">
              <span class="caption">Summary</span>
              <span class="box-value box-value-plain">{{ selected.subtitle }}</span>
            </div>
            <div class="box box-full">
              <span class="caption">Policy</span>
              <span class="box-value">{{ selected.policy_label }}</span>
            </div>
            <div class="box box-full">
              <span class="caption">Plan type</span>
              <span class="box-value">{{ planTypeLabel(selected.plan_type) }}</span>
            </div>
          </div>
          <fieldset class="urgency">
            <legend class="form-legend">Urgency</legend>
            <label class="choice">
              <input v-model="urgency" type="radio" name="urgency" value="standard" />
              <span>Standard — decision within 7 calendar days</span>
            </label>
            <label class="choice">
              <input v-model="urgency" type="radio" name="urgency" value="expedited" />
              <span>Expedited — decision within 72 hours</span>
            </label>
            <p class="hint">Expedited requests use a 72-hour CMS decision deadline.</p>
          </fieldset>
          <div class="confirm-actions">
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              <LoaderCircle v-if="submitting" :size="15" class="spin" aria-hidden="true" />
              {{ submitting ? 'Submitting…' : 'Submit request' }}
            </button>
            <button type="button" class="btn btn-quiet" :disabled="submitting" @click="cancel">Cancel</button>
          </div>
        </form>
        <div v-else class="absence">
          <h2 class="section-title">No scenario selected</h2>
          <p>Select a scenario to review its policy and plan, then choose the urgency.</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.intake {
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(18rem, 5fr);
  gap: var(--space-5);
  align-items: start;
}

.scenarios {
  display: grid;
  margin: 0;
  padding: 0;
  border-top: 1px solid var(--rule-strong);
  list-style: none;
}

.scenarios > li {
  border-bottom: 1px solid var(--rule);
}

.scenario {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 100%;
  padding: 0.75rem 0.75rem 0.75rem 0.875rem;
  border: 0;
  background: var(--paper);
  text-align: left;
  cursor: pointer;
  transition: background-color var(--tint);
}

.scenario:hover {
  background: var(--action-wash);
}

.scenario[aria-pressed='true'] {
  background: var(--action-wash-2);
  box-shadow: inset 0 0 0 1px var(--action);
}

.scenario > svg {
  flex: none;
  color: var(--ink-3);
}

.scenario-text {
  display: grid;
  gap: 0.1875rem;
  min-width: 0;
  flex: 1;
}

.scenario-title {
  font-weight: 700;
}

.scenario-subtitle {
  color: var(--ink-2);
}

.scenario-meta {
  color: var(--ink-3);
  font-size: var(--text-small);
  font-weight: 600;
}

.scenario-skeleton {
  display: grid;
  gap: 0.5rem;
  padding: 0.875rem;
  background: var(--paper);
}

.confirm {
  position: sticky;
  top: var(--space-4);
}

.confirm-form {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
}

.confirm-title {
  font-size: var(--text-h3);
}

.confirm-title:focus-visible {
  outline-offset: 4px;
}

.urgency {
  display: grid;
  gap: 0.125rem;
}

.confirm-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--rule);
}

@media (max-width: 56rem) {
  .intake {
    grid-template-columns: 1fr;
  }

  .confirm {
    position: static;
  }
}
</style>

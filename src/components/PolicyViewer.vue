<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { ExternalLink, LoaderCircle, X } from '@lucide/vue';
import { formatDate } from '../format';
import { loadPolicy } from '../policies';
import type { PolicyDocument } from '../types';

// The coverage policy text, opened inline under the policy basis so the
// reviewer keeps the case in view. No dialog, no side sheet.
const props = defineProps<{
  policyId: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

const policy = ref<PolicyDocument | null>(null);

const loading = ref(true);

const failed = ref(false);

const heading = ref<HTMLHeadingElement | null>(null);

const sourceLabel = computed(() =>
  policy.value?.source_type === 'lcd' ? 'CMS Local Coverage Determination' : 'CMS National Coverage Determination',
);

const facts = computed(() => {
  const current = policy.value;

  if (!current) return [];

  const rows = [
    { label: 'Source', value: sourceLabel.value },
    { label: 'Version', value: current.version },
    { label: 'Contractor', value: current.contractor },
    { label: 'Effective', value: current.effective_date ? formatDate(current.effective_date) : null },
    { label: 'Last updated', value: current.last_updated ? formatDate(current.last_updated) : null },
    { label: 'Benefit category', value: current.benefit_category },
    { label: 'Coverage model', value: current.coverage_model },
  ];

  return rows.flatMap((row) => (row.value ? [{ label: row.label, value: row.value }] : []));
});

async function load(): Promise<void> {
  loading.value = true;
  failed.value = false;
  policy.value = await loadPolicy(props.policyId);
  failed.value = policy.value === null;
  loading.value = false;
  await nextTick();
  heading.value?.focus();
}

watch(() => props.policyId, load, { immediate: true });
</script>

<template>
  <section class="policy" aria-labelledby="policy-viewer-title" :aria-busy="loading">
    <header class="policy-head">
      <h4 id="policy-viewer-title" ref="heading" tabindex="-1" class="policy-title">
        <template v-if="policy">{{ policy.code }} — {{ policy.title }}</template>
        <template v-else>Coverage policy</template>
      </h4>
      <button type="button" class="btn btn-quiet btn-small" @click="emit('close')">
        <X :size="14" aria-hidden="true" />
        Close policy
      </button>
    </header>

    <p v-if="loading" class="policy-loading" role="status">
      <LoaderCircle :size="15" class="spin" aria-hidden="true" />
      Loading policy text…
    </p>

    <p v-else-if="failed" class="field-error" role="alert">The policy text could not be loaded. Try again in a moment.</p>

    <template v-else-if="policy">
      <p class="policy-summary">{{ policy.summary }}</p>

      <dl class="facts">
        <template v-for="fact in facts" :key="fact.label">
          <dt>{{ fact.label }}</dt>
          <dd>{{ fact.value }}</dd>
        </template>
      </dl>

      <div v-if="policy.criteria.length > 0" class="policy-block">
        <h5 class="policy-block-title">Coverage criteria</h5>
        <ol class="policy-criteria">
          <li v-for="criterion in policy.criteria" :key="criterion.id">
            <p class="criterion-line">
              <span class="criterion-id num">{{ criterion.id }}</span>
              <span>{{ criterion.text }}</span>
            </p>
            <p class="criterion-meta caption">
              <span v-if="criterion.category">{{ criterion.category }}</span>
              <span>{{ criterion.required ? 'Required' : 'Optional' }}</span>
              <span v-if="criterion.logic">{{ criterion.logic }}</span>
            </p>
            <ul v-if="criterion.options.length > 0" class="criterion-options">
              <li v-for="(option, index) in criterion.options" :key="index">{{ option }}</li>
            </ul>
          </li>
        </ol>
      </div>

      <div v-if="policy.non_covered.length > 0" class="policy-block">
        <h5 class="policy-block-title">Not covered</h5>
        <ul class="policy-list">
          <li v-for="(item, index) in policy.non_covered" :key="index">{{ item }}</li>
        </ul>
      </div>

      <div v-if="policy.notes.length > 0" class="policy-block">
        <h5 class="policy-block-title">Notes</h5>
        <ul class="policy-list">
          <li v-for="(note, index) in policy.notes" :key="index">{{ note }}</li>
        </ul>
      </div>

      <div v-for="section in policy.sections" :key="section.key" class="policy-block">
        <h5 class="policy-block-title">{{ section.title }}</h5>
        <p v-for="(paragraph, index) in section.paragraphs" :key="index" class="policy-paragraph">{{ paragraph }}</p>
      </div>

      <div class="policy-links">
        <a v-if="policy.source_url" class="btn btn-small" :href="policy.source_url" target="_blank" rel="noopener noreferrer">
          <ExternalLink :size="14" aria-hidden="true" />
          Open on cms.gov
        </a>
        <a v-if="policy.api_url" class="btn btn-quiet btn-small" :href="policy.api_url" target="_blank" rel="noopener noreferrer">
          <ExternalLink :size="14" aria-hidden="true" />
          CMS Coverage API record
        </a>
      </div>
    </template>
  </section>
</template>

<style scoped>
.policy {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--surface);
  animation: policy-in 180ms var(--ease-out);
}

.policy-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2) var(--space-4);
}

.policy-title {
  font-size: var(--text-body);
  line-height: 1.35;
}

.policy-title:focus-visible {
  outline-offset: 3px;
}

.policy-loading {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  color: var(--ink-2);
}

.policy-summary {
  max-width: 72ch;
}

.policy-block {
  display: grid;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--rule);
}

.policy-block-title {
  font-size: var(--text-small);
  font-weight: 700;
}

.policy-criteria {
  display: grid;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.criterion-line {
  display: flex;
  gap: 0.625rem;
  max-width: 72ch;
}

.criterion-id {
  flex: none;
  min-width: 3.5rem;
  color: var(--ink-2);
  font-weight: 700;
}

.criterion-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0 var(--space-3);
  padding-left: calc(3.5rem + 0.625rem);
}

.criterion-options,
.policy-list {
  display: grid;
  gap: 0.25rem;
  margin: 0;
  padding-left: 1.25rem;
  max-width: 72ch;
  font-size: var(--text-small);
}

.criterion-options {
  margin-left: calc(3.5rem + 0.625rem);
}

.policy-paragraph {
  max-width: 72ch;
  font-size: var(--text-small);
  color: var(--ink-2);
}

.policy-links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

@keyframes policy-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
}
</style>

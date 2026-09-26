<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Braces, CircleCheck, LoaderCircle, TriangleAlert } from '@lucide/vue';
import { formatDateTime } from '../format';
import { useAppStore } from '../store';
import type { JsonValue, LlmTrace } from '../types';

// The exact prompt, payload, and response behind a recommendation, so a
// reviewer or auditor can see what the engine was shown and what it said.
const props = defineProps<{
  requestId: string;
  finalEngineLabel: string;
}>();

const store = useAppStore();

const loading = ref(false);

const inspection = computed(() => {
  const current = store.state.currentLlmInspection;

  return current?.request_id === props.requestId ? current : null;
});

const traceCount = computed(() => {
  const count = inspection.value?.traces.length ?? 0;

  return `${count} engine call${count === 1 ? '' : 's'}`;
});

const emptyCopy = computed(() => {
  if (inspection.value?.final_engine === 'offline') {
    return 'No model or network request was sent. The rules engine checked each criterion locally.';
  }

  return 'No engine request was captured for this recommendation.';
});

watch(
  () => props.requestId,
  () => {
    loading.value = false;
  },
);

async function load(): Promise<void> {
  loading.value = true;
  await store.loadLlmInspection(props.requestId);
  loading.value = false;
}

function providerLabel(trace: LlmTrace): string {
  return trace.provider === 'bedrock' ? 'Anthropic Claude via Bedrock' : 'OpenAI GPT via Codex CLI';
}

function modelLabel(trace: LlmTrace): string {
  return trace.model_id || 'Configured provider default';
}

function prettyJson(value: { [key: string]: JsonValue } | null): string {
  if (value === null) return 'null';

  return JSON.stringify(value, null, 2);
}
</script>

<template>
  <section class="inspector" aria-labelledby="inspector-title">
    <header class="inspector-head">
      <div>
        <h3 id="inspector-title" class="inspector-title">Engine calls</h3>
        <p class="caption">{{ finalEngineLabel }}</p>
      </div>
      <span v-if="inspection" class="caption num">{{ traceCount }}</span>
      <button v-else type="button" class="btn btn-small" :disabled="loading" @click="load">
        <LoaderCircle v-if="loading" :size="14" class="spin" aria-hidden="true" />
        <Braces v-else :size="14" aria-hidden="true" />
        {{ loading ? 'Loading engine calls…' : 'Load engine calls' }}
      </button>
    </header>

    <p v-if="inspection && inspection.traces.length === 0" class="inspector-empty">{{ emptyCopy }}</p>

    <article
      v-for="(trace, index) in inspection?.traces ?? []"
      :key="`${trace.provider}-${trace.created_at}-${index}`"
      class="trace"
      :class="{ 'trace-failed': trace.status === 'failed' }"
      :aria-labelledby="`trace-title-${index}`"
    >
      <header class="trace-head">
        <div>
          <h4 :id="`trace-title-${index}`" class="trace-title">{{ trace.engine_label }}</h4>
          <p class="caption">{{ providerLabel(trace) }}</p>
        </div>
        <span class="code" :class="{ 'code-flag-soft': trace.status === 'failed' }">
          <CircleCheck v-if="trace.status === 'succeeded'" :size="13" aria-hidden="true" />
          <TriangleAlert v-else :size="13" aria-hidden="true" />
          {{ trace.status === 'succeeded' ? 'Succeeded' : 'Failed' }}
        </span>
      </header>

      <dl class="facts trace-facts">
        <dt>Model</dt>
        <dd class="num">{{ modelLabel(trace) }}</dd>
        <dt>Captured</dt>
        <dd class="num">{{ formatDateTime(trace.created_at) }}</dd>
        <dt>Evaluation</dt>
        <dd class="num">{{ inspection?.evaluation_id }}</dd>
      </dl>

      <p v-if="trace.error" class="field-error">
        <TriangleAlert :size="15" aria-hidden="true" />
        {{ trace.error }}
      </p>

      <div v-if="trace.redactions.length > 0" class="redactions">
        <p class="caption">Redacted before display</p>
        <ul>
          <li v-for="redaction in trace.redactions" :key="redaction">{{ redaction }}</li>
        </ul>
      </div>

      <div class="trace-sections">
        <details v-if="trace.prompt">
          <summary>Prompt</summary>
          <pre>{{ trace.prompt }}</pre>
        </details>
        <details>
          <summary>Request payload</summary>
          <pre>{{ prettyJson(trace.request_payload) }}</pre>
        </details>
        <details>
          <summary>Raw response</summary>
          <pre>{{ trace.raw_response || '(empty)' }}</pre>
        </details>
        <details v-if="trace.parsed_response">
          <summary>Parsed JSON</summary>
          <pre>{{ prettyJson(trace.parsed_response) }}</pre>
        </details>
      </div>
    </article>
  </section>
</template>

<style scoped>
.inspector {
  display: grid;
  gap: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--rule);
}

.inspector-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2) var(--space-4);
}

.inspector-title {
  font-size: var(--text-body);
}

.inspector-empty {
  color: var(--ink-2);
  font-size: var(--text-small);
}

.trace {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4) var(--space-4);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
}

.trace-failed {
  border-color: var(--flag);
}

.trace-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.trace-title {
  font-size: var(--text-body);
}

.redactions ul {
  margin: 0.25rem 0 0;
  padding-left: 1.125rem;
  font-size: var(--text-small);
}

.trace-sections {
  display: grid;
  border: 1px solid var(--rule);
  border-radius: var(--radius);
}

.trace-sections details + details {
  border-top: 1px solid var(--rule);
}

.trace-sections summary {
  padding: 0.5rem 0.75rem;
  font-size: var(--text-small);
  font-weight: 700;
  cursor: pointer;
  transition: background-color var(--tint);
}

.trace-sections summary:hover {
  background: var(--action-wash);
}

.trace-sections pre {
  max-height: 24rem;
  margin: 0;
  overflow: auto;
  padding: var(--space-3);
  border-top: 1px solid var(--rule);
  background: var(--sunk);
  font-family: var(--font-code);
  font-size: var(--text-caption);
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>

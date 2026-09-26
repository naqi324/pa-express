<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { Check, ChevronDown, ChevronUp, CircleCheck, RefreshCw, SlidersHorizontal, TriangleAlert } from '@lucide/vue';
import { ENGINE_ORDER, ENGINE_PRESENTATION, effortLabel } from '../enginePresentation';
import { useAppStore } from '../store';
import type { AuthMethod, ClaudeConfig, EngineConfig, EngineId, EngineInfo, OpenAiGptConfig } from '../types';
import ConfigureEngineForm from './ConfigureEngineForm.vue';

const store = useAppStore();

const { state } = store;

const configuring = ref<EngineId | null>(null);

const openConfig = computed(() => state.engineConfig.find((entry) => entry.engine === configuring.value) ?? null);

const engines = computed(() =>
  state.engines.toSorted((left, right) => ENGINE_ORDER.indexOf(left.id) - ENGINE_ORDER.indexOf(right.id)),
);

onMounted(() => {
  void store.refreshHealth();
  void store.refreshEngineConfig();

  if (state.engines.length === 0) void store.refreshEngines();
});

function checkStatus(): void {
  void store.refreshEngines();
  void store.refreshHealth();
  void store.refreshEngineConfig();
}

function engineConfig(engine: EngineInfo): EngineConfig | undefined {
  return state.engineConfig.find((entry) => entry.engine === engine.id);
}

interface ProviderFact {
  label: string;
  value: string;
}

function modelLabel(config: EngineConfig, modelId: string): string {
  return config.models.find((model) => model.id === modelId)?.label ?? modelId;
}

function methodLabel(config: EngineConfig, method: AuthMethod): string {
  return config.auth_methods.find((option) => option.id === method)?.label ?? method;
}

function keyDetail(hint: string | null): string {
  if (!hint) return 'no key entered';

  return hint === 'set' ? 'key stored' : `key ${hint}`;
}

function claudeConnection(config: EngineConfig, claude: ClaudeConfig): string {
  const label = methodLabel(config, claude.auth_method);

  if (claude.auth_method === 'api_key') return `${label} · ${keyDetail(claude.api_key_hint)}`;

  if (claude.auth_method === 'cli') return `${label} · ${claude.command}`;

  const hint = claude.access_key_id_hint ? ` ${claude.access_key_id_hint}` : '';

  const profile = claude.aws_profile ? `profile ${claude.aws_profile}` : 'default credential chain';

  const credentials = claude.bedrock_credentials === 'access_keys' ? `access keys${hint}` : profile;

  return `${label} · ${credentials} · ${claude.bedrock_region}`;
}

function openAiGptConnection(config: EngineConfig, gpt: OpenAiGptConfig): string {
  const label = methodLabel(config, gpt.auth_method);

  return gpt.auth_method === 'api_key' ? `${label} · ${keyDetail(gpt.api_key_hint)}` : `${label} · ${gpt.command}`;
}

function providerFacts(engine: EngineInfo): ProviderFact[] {
  const config = engineConfig(engine);

  if (!config) return [];

  if (config.anthropic_claude) {
    const claude = config.anthropic_claude;

    return [
      { label: 'Connection', value: claudeConnection(config, claude) },
      { label: 'Model', value: modelLabel(config, claude.model_id) },
      { label: 'Reasoning', value: effortLabel(claude.effort) },
    ];
  }

  if (config.openai_gpt) {
    const gpt = config.openai_gpt;

    return [
      { label: 'Connection', value: openAiGptConnection(config, gpt) },
      { label: 'Model', value: modelLabel(config, gpt.model_id) },
      { label: 'Reasoning', value: effortLabel(gpt.effort) },
    ];
  }

  if (engine.model_id) return [{ label: 'Model', value: engine.model_id }];

  return [];
}

function isConfigurable(engine: EngineInfo): boolean {
  return (engineConfig(engine)?.auth_methods.length ?? 0) > 0;
}

function isOverridden(engine: EngineInfo): boolean {
  const config = engineConfig(engine);

  return config?.anthropic_claude?.is_override || config?.openai_gpt?.is_override || false;
}

function statusLine(engine: EngineInfo): string {
  if (engine.available) return ENGINE_PRESENTATION[engine.id].readyNote;

  return `Needs setup — ${engine.availability_note}`;
}

function chooseDefault(engine: EngineInfo): void {
  if (!engine.available || state.defaultEngine === engine.id) return;

  store.setDefaultEngine(engine.id);
}

function toggleConfigure(engine: EngineInfo): void {
  configuring.value = configuring.value === engine.id ? null : engine.id;
}

async function closeConfigure(engine: EngineInfo): Promise<void> {
  configuring.value = null;
  await nextTick();
  document.getElementById(`configure-toggle-${engine.id}`)?.focus();
}
</script>

<template>
  <section class="page" aria-labelledby="connection-title">
    <div class="page-head">
      <div class="page-head-text">
        <h1 id="connection-title">Reasoning engine</h1>
        <p class="muted">Choose the engine used to reason over new requests.</p>
      </div>
      <div class="page-head-actions">
        <button type="button" class="btn btn-quiet" @click="checkStatus">
          <RefreshCw :size="15" aria-hidden="true" />
          Check status
        </button>
      </div>
    </div>

    <p class="notice" :class="{ 'notice-flag': !state.health }" role="status">
      <CircleCheck v-if="state.health" :size="16" aria-hidden="true" />
      <TriangleAlert v-else :size="16" aria-hidden="true" />
      <span v-if="state.health" class="notice-body num">Backend connected — v{{ state.health.version }}.</span>
      <span v-else class="notice-body">
        Backend unreachable — run <code>pnpm dev:backend</code> (port 8004), then select Check status.
      </span>
    </p>

    <fieldset class="engines">
      <legend class="section-title">Engine for new requests</legend>
      <div v-if="engines.length === 0" class="absence">
        <p>No engines reported yet. Start the backend, then select Check status.</p>
      </div>

      <div
        v-for="engine in engines"
        :key="engine.id"
        class="engine"
        :class="{ 'is-current': state.defaultEngine === engine.id, 'is-unavailable': !engine.available }"
      >
        <div class="engine-row">
          <label class="engine-pick">
            <input
              type="radio"
              name="default-engine"
              :value="engine.id"
              :checked="state.defaultEngine === engine.id"
              :disabled="!engine.available"
              :aria-describedby="`engine-status-${engine.id}`"
              @change="chooseDefault(engine)"
            />
            <span class="engine-text">
              <span class="engine-name">{{ ENGINE_PRESENTATION[engine.id].name }}</span>
              <span class="engine-tagline">{{ ENGINE_PRESENTATION[engine.id].tagline }}</span>
            </span>
          </label>

          <span class="code" :class="{ 'code-flag-soft': !engine.available }">
            <CircleCheck v-if="engine.available" :size="13" aria-hidden="true" />
            <TriangleAlert v-else :size="13" aria-hidden="true" />
            {{ engine.available ? 'Ready' : 'Needs setup' }}
          </span>
        </div>

        <div class="engine-detail">
          <p class="engine-how">{{ ENGINE_PRESENTATION[engine.id].how }}</p>
          <p :id="`engine-status-${engine.id}`" class="engine-status" :class="{ 'is-flag': !engine.available }">
            {{ statusLine(engine) }}
          </p>

          <dl v-if="providerFacts(engine).length > 0" class="facts engine-facts">
            <template v-for="fact in providerFacts(engine)" :key="fact.label">
              <dt>{{ fact.label }}</dt>
              <dd class="num">{{ fact.value }}</dd>
            </template>
          </dl>

          <div class="engine-actions">
            <p v-if="state.defaultEngine === engine.id" class="engine-current">
              <Check :size="14" aria-hidden="true" />
              Current engine — new requests start here.
            </p>
            <span v-if="isOverridden(engine)" class="code code-action">Session override</span>
            <button
              v-if="isConfigurable(engine)"
              :id="`configure-toggle-${engine.id}`"
              type="button"
              class="btn btn-small btn-quiet"
              :aria-expanded="configuring === engine.id"
              :aria-controls="`configure-panel-${engine.id}`"
              @click="toggleConfigure(engine)"
            >
              <SlidersHorizontal :size="14" aria-hidden="true" />
              Connection &amp; model
              <ChevronUp v-if="configuring === engine.id" :size="14" aria-hidden="true" />
              <ChevronDown v-else :size="14" aria-hidden="true" />
            </button>
          </div>

          <div v-if="openConfig?.engine === engine.id" :id="`configure-panel-${engine.id}`">
            <ConfigureEngineForm :config="openConfig" @close="closeConfigure(engine)" />
          </div>
        </div>
      </div>
    </fieldset>
  </section>
</template>

<style scoped>
.engines {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.engine {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
  transition:
    border-color var(--tint),
    background-color var(--tint);
}

.engine.is-current {
  border-color: var(--action);
  background: var(--action-wash);
}

.engine-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.engine-pick {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  min-width: 0;
  cursor: pointer;
}

.engine-pick input {
  flex: none;
  width: 1.125rem;
  height: 1.125rem;
  margin: 0.25rem 0 0;
  accent-color: var(--action);
}

.is-unavailable .engine-pick {
  cursor: not-allowed;
}

.engine-text {
  display: grid;
  gap: 0.125rem;
}

.engine-name {
  font-size: var(--text-h3);
  font-weight: 700;
  line-height: 1.3;
}

.engine-tagline {
  color: var(--ink-2);
}

.engine-detail {
  display: grid;
  gap: var(--space-2);
  padding-left: calc(1.125rem + 0.75rem);
}

.engine-how {
  max-width: 72ch;
  font-size: var(--text-small);
}

.engine-status {
  color: var(--ink-2);
  font-size: var(--text-small);
}

.engine-status.is-flag {
  color: var(--flag-deep);
  font-weight: 600;
}

.engine-facts {
  margin-top: var(--space-1);
}

.engine-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  min-height: var(--control-height);
}

.engine-current {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--action-deep);
  font-size: var(--text-small);
  font-weight: 600;
}

@media (max-width: 40rem) {
  .engine-row {
    flex-direction: column;
  }

  .engine-detail {
    padding-left: 0;
  }
}
</style>

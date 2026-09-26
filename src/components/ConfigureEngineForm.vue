<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { LoaderCircle, RotateCw, Save, TriangleAlert } from '@lucide/vue';
import {
  BEDROCK_REGIONS,
  CLAUDE_EFFORTS,
  CLAUDE_MODELS,
  ENGINE_PRESENTATION,
  OPENAI_GPT_EFFORTS,
  OPENAI_GPT_MODELS,
} from '../enginePresentation';
import { useAppStore } from '../store';
import { notify } from '../toast';
import type {
  BedrockAuthMethod,
  ClaudeModelId,
  ClaudeReasoningEffort,
  EngineConfig,
  OpenAiGptModelId,
  OpenAiReasoningEffort,
} from '../types';

// Session-only provider settings, opened inline under the engine row.
const props = defineProps<{
  config: EngineConfig;
}>();

const emit = defineEmits<{
  close: [];
}>();

interface ClaudeForm {
  authMethod: BedrockAuthMethod;
  region: string;
  modelId: ClaudeModelId;
  effort: ClaudeReasoningEffort;
  awsProfile: string;
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken: string;
}

interface OpenAiGptForm {
  command: string;
  modelId: OpenAiGptModelId;
  effort: OpenAiReasoningEffort;
}

const store = useAppStore();

const name = computed(() => ENGINE_PRESENTATION[props.config.engine].name);

const formId = computed(() => `configure-${props.config.engine}`);

const claude = reactive<ClaudeForm>({
  authMethod: 'profile',
  region: 'us-west-2',
  modelId: 'us.anthropic.claude-sonnet-5',
  effort: 'high',
  awsProfile: '',
  accessKeyId: '',
  secretAccessKey: '',
  sessionToken: '',
});

const openaiGpt = reactive<OpenAiGptForm>({
  command: 'codex',
  modelId: 'gpt-5.5',
  effort: 'xhigh',
});

const touched = ref(false);

const saving = ref(false);

const resetting = ref(false);

// Seed the form from the current (possibly overridden) config each time it opens.
watch(
  () => props.config,
  (config) => {
    if (config.anthropic_claude) {
      claude.authMethod = config.anthropic_claude.auth_method;
      claude.region = config.anthropic_claude.region;
      claude.modelId = config.anthropic_claude.model_id;
      claude.effort = config.anthropic_claude.effort;
      claude.awsProfile = config.anthropic_claude.aws_profile;
      // Secrets are never returned; always start blank and only send when filled.
      claude.accessKeyId = '';
      claude.secretAccessKey = '';
      claude.sessionToken = '';
    }

    if (config.openai_gpt) {
      openaiGpt.command = config.openai_gpt.command;
      openaiGpt.modelId = config.openai_gpt.model_id;
      openaiGpt.effort = config.openai_gpt.effort;
    }

    touched.value = false;
  },
  { immediate: true },
);

const needsKeys = computed(() => props.config.auth_style === 'aws_bedrock' && claude.authMethod === 'access_keys');

// When switching to access keys, keys are required unless already stored server-side.
const keysAlreadyStored = computed(() => props.config.anthropic_claude?.access_keys_configured ?? false);

const keysMissing = computed(
  () => needsKeys.value && !keysAlreadyStored.value && (!claude.accessKeyId.trim() || !claude.secretAccessKey.trim()),
);

const showKeysError = computed(() => touched.value && keysMissing.value);

const isOverride = computed(
  () => props.config.anthropic_claude?.is_override || props.config.openai_gpt?.is_override || false,
);

async function saveClaude(): Promise<boolean> {
  return store.saveAnthropicClaudeConfig({
    auth_method: claude.authMethod,
    region: claude.region.trim(),
    model_id: claude.modelId,
    effort: claude.effort,
    aws_profile: claude.awsProfile.trim() || null,
    aws_access_key_id: claude.accessKeyId.trim() || null,
    aws_secret_access_key: claude.secretAccessKey.trim() || null,
    aws_session_token: claude.sessionToken.trim() || null,
  });
}

async function saveOpenAiGpt(): Promise<boolean> {
  return store.saveOpenAiGptConfig({
    command: 'codex',
    model_id: openaiGpt.modelId,
    effort: openaiGpt.effort,
  });
}

async function save(): Promise<void> {
  touched.value = true;

  if (props.config.engine === 'anthropic_claude' && keysMissing.value) return;

  if (props.config.engine === 'offline') return;

  saving.value = true;

  const ok = props.config.engine === 'anthropic_claude' ? await saveClaude() : await saveOpenAiGpt();

  saving.value = false;

  if (!ok) return;

  notify('success', `${name.value} provider settings saved for this session.`);
  emit('close');
}

async function resetToDefaults(): Promise<void> {
  resetting.value = true;

  const ok =
    props.config.engine === 'anthropic_claude'
      ? await store.resetAnthropicClaudeConfig()
      : await store.resetOpenAiGptConfig();

  resetting.value = false;

  if (!ok) return;

  notify('success', `${name.value} reset to the server defaults.`);
  emit('close');
}
</script>

<template>
  <form class="configure" novalidate @submit.prevent="save">
    <p class="configure-intro">
      These settings apply to <strong>{{ name }}</strong> for this browser session only. They are held in server
      memory — never written to disk or logged — and cleared when the backend restarts. Claude uses Bedrock credentials;
      GPT uses the local Codex CLI.
    </p>

    <div v-if="config.engine === 'anthropic_claude'" class="configure-fields">
      <div class="form-field">
        <label :for="`${formId}-model`">Model</label>
        <select :id="`${formId}-model`" v-model="claude.modelId" class="select num">
          <option v-for="model in CLAUDE_MODELS" :key="model" :value="model">{{ model }}</option>
        </select>
      </div>

      <div class="form-field">
        <label :for="`${formId}-effort`">Reasoning effort</label>
        <select
          :id="`${formId}-effort`"
          v-model="claude.effort"
          class="select"
          :aria-describedby="`${formId}-effort-hint`"
        >
          <option v-for="option in CLAUDE_EFFORTS" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
        <p :id="`${formId}-effort-hint`" class="hint">Sent to Bedrock as Claude adaptive thinking effort.</p>
      </div>

      <fieldset class="configure-wide">
        <legend class="form-legend">Authentication method</legend>
        <label class="choice">
          <input v-model="claude.authMethod" type="radio" :name="`${formId}-auth`" value="profile" />
          <span>Shared AWS profile (server credentials)</span>
        </label>
        <label class="choice">
          <input v-model="claude.authMethod" type="radio" :name="`${formId}-auth`" value="access_keys" />
          <span>AWS access keys (entered here, this session)</span>
        </label>
      </fieldset>

      <div v-if="claude.authMethod === 'profile'" class="form-field configure-wide">
        <label :for="`${formId}-profile`">AWS profile name</label>
        <input
          :id="`${formId}-profile`"
          v-model="claude.awsProfile"
          class="input"
          type="text"
          autocomplete="off"
          spellcheck="false"
          :aria-describedby="`${formId}-profile-hint`"
        />
        <p :id="`${formId}-profile-hint`" class="hint">
          Named profile from the server's AWS credentials file (leave blank to use the standard AWS credential chain).
        </p>
      </div>

      <template v-else>
        <div class="form-field">
          <label :for="`${formId}-key-id`">AWS access key ID</label>
          <input
            :id="`${formId}-key-id`"
            v-model="claude.accessKeyId"
            class="input"
            type="text"
            autocomplete="off"
            spellcheck="false"
            :aria-invalid="showKeysError"
            :aria-describedby="keysAlreadyStored ? `${formId}-keys-hint` : showKeysError ? `${formId}-keys-error` : undefined"
          />
          <p v-if="keysAlreadyStored" :id="`${formId}-keys-hint`" class="hint">
            Keys are stored for this session; leave blank to keep them.
          </p>
        </div>

        <div class="form-field">
          <label :for="`${formId}-secret`">AWS secret access key</label>
          <input
            :id="`${formId}-secret`"
            v-model="claude.secretAccessKey"
            class="input"
            type="password"
            autocomplete="new-password"
            :aria-invalid="showKeysError"
            :aria-describedby="showKeysError ? `${formId}-keys-error` : undefined"
          />
        </div>

        <p v-if="showKeysError" :id="`${formId}-keys-error`" class="field-error configure-wide" role="alert">
          <TriangleAlert :size="15" aria-hidden="true" />
          Access key ID and secret are required.
        </p>

        <div class="form-field configure-wide">
          <label :for="`${formId}-token`">AWS session token (optional)</label>
          <input
            :id="`${formId}-token`"
            v-model="claude.sessionToken"
            class="input"
            type="password"
            autocomplete="new-password"
            :aria-describedby="`${formId}-token-hint`"
          />
          <p :id="`${formId}-token-hint`" class="hint">Only needed for temporary STS credentials.</p>
        </div>
      </template>

      <div class="form-field">
        <label :for="`${formId}-region`">Region</label>
        <input
          :id="`${formId}-region`"
          v-model="claude.region"
          class="input num"
          type="text"
          :list="`${formId}-regions`"
          autocomplete="off"
          spellcheck="false"
        />
        <datalist :id="`${formId}-regions`">
          <option v-for="region in BEDROCK_REGIONS" :key="region" :value="region" />
        </datalist>
      </div>
    </div>

    <div v-else-if="config.engine === 'openai_gpt'" class="configure-fields">
      <div class="form-field">
        <label :for="`${formId}-model`">Model</label>
        <select :id="`${formId}-model`" v-model="openaiGpt.modelId" class="select num">
          <option v-for="model in OPENAI_GPT_MODELS" :key="model" :value="model">{{ model }}</option>
        </select>
      </div>

      <div class="form-field">
        <label :for="`${formId}-effort`">Reasoning effort</label>
        <select :id="`${formId}-effort`" v-model="openaiGpt.effort" class="select">
          <option v-for="option in OPENAI_GPT_EFFORTS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>

      <dl class="facts configure-wide">
        <dt>Runtime</dt>
        <dd class="num">{{ openaiGpt.command }} CLI</dd>
      </dl>
    </div>

    <div class="configure-actions">
      <button type="submit" class="btn btn-primary" :disabled="saving || resetting">
        <LoaderCircle v-if="saving" :size="15" class="spin" aria-hidden="true" />
        <Save v-else :size="15" aria-hidden="true" />
        {{ saving ? 'Saving…' : 'Save for this session' }}
      </button>
      <button v-if="isOverride" type="button" class="btn btn-quiet" :disabled="saving || resetting" @click="resetToDefaults">
        <LoaderCircle v-if="resetting" :size="15" class="spin" aria-hidden="true" />
        <RotateCw v-else :size="15" aria-hidden="true" />
        {{ resetting ? 'Resetting…' : 'Reset to server default' }}
      </button>
      <button type="button" class="btn" :disabled="saving" @click="emit('close')">Cancel</button>
    </div>
  </form>
</template>

<style scoped>
.configure {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  background: var(--surface);
  animation: configure-in 180ms var(--ease-out);
}

.configure-intro {
  max-width: 72ch;
  color: var(--ink-2);
  font-size: var(--text-small);
}

.configure-intro strong {
  color: var(--ink);
}

.configure-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  align-items: start;
}

.configure-wide {
  grid-column: 1 / -1;
}

.configure-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--rule);
}

@media (max-width: 40rem) {
  .configure-fields {
    grid-template-columns: 1fr;
  }
}

@keyframes configure-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
}
</style>

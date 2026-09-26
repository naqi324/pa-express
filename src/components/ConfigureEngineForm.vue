<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { LoaderCircle, RotateCw, Save, TriangleAlert } from '@lucide/vue';
import { BEDROCK_REGIONS, EFFORT_LABELS, ENGINE_PRESENTATION, effortHint, methodSupport } from '../enginePresentation';
import { useAppStore } from '../store';
import { notify } from '../toast';
import type { AuthMethod, AuthMethodOption, BedrockCredentials, EngineConfig, ReasoningEffort } from '../types';

// Session-only provider settings, opened inline under the engine row. The
// connections, models, and efforts it offers all come from the backend catalog.
const props = defineProps<{
  config: EngineConfig;
}>();

const emit = defineEmits<{
  close: [];
}>();

interface ProviderForm {
  authMethod: AuthMethod;
  modelId: string;
  effort: ReasoningEffort | null;
  apiKey: string;
  bedrockRegion: string;
  bedrockCredentials: BedrockCredentials;
  awsProfile: string;
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken: string;
}

const store = useAppStore();

const name = computed(() => ENGINE_PRESENTATION[props.config.engine].name);

const formId = computed(() => `configure-${props.config.engine}`);

const form = reactive<ProviderForm>({
  authMethod: 'cli',
  modelId: '',
  effort: null,
  apiKey: '',
  bedrockRegion: 'us-west-2',
  bedrockCredentials: 'profile',
  awsProfile: '',
  accessKeyId: '',
  secretAccessKey: '',
  sessionToken: '',
});

const touched = ref(false);

const saving = ref(false);

const resetting = ref(false);

const current = computed(() => props.config.anthropic_claude ?? props.config.openai_gpt);

// Seed the form from the current (possibly overridden) config each time it opens.
watch(
  () => props.config,
  (config) => {
    const view = config.anthropic_claude ?? config.openai_gpt;

    if (view) {
      form.authMethod = view.auth_method;
      form.modelId = view.model_id;
      form.effort = view.effort;
    }

    if (config.anthropic_claude) {
      form.bedrockRegion = config.anthropic_claude.bedrock_region;
      form.bedrockCredentials = config.anthropic_claude.bedrock_credentials;
      form.awsProfile = config.anthropic_claude.aws_profile;
    }

    // Secrets are never returned; always start blank and only send what is typed.
    form.apiKey = '';
    form.accessKeyId = '';
    form.secretAccessKey = '';
    form.sessionToken = '';
    touched.value = false;
  },
  { immediate: true },
);

const chosenMethod = computed(() => props.config.auth_methods.find((method) => method.id === form.authMethod));

const selectedModel = computed(() => props.config.models.find((model) => model.id === form.modelId));

const support = computed(() => methodSupport(selectedModel.value, form.authMethod));

const modelsForMethod = computed(() =>
  props.config.models.filter((model) => methodSupport(model, form.authMethod) !== undefined),
);

const efforts = computed(() => support.value?.efforts ?? []);

// Keep the model when the new connection offers it; otherwise take its first model.
watch(
  () => form.authMethod,
  (method) => {
    if (methodSupport(selectedModel.value, method)) return;

    const fallback = modelsForMethod.value[0];

    if (fallback) form.modelId = fallback.id;
  },
);

// Keep the effort when the new model takes it; otherwise take the model's default.
watch(support, (next) => {
  if (!next) return;

  if (form.effort !== null && next.efforts.includes(form.effort)) return;

  form.effort = next.default_effort;
});

function effortOptionLabel(effort: ReasoningEffort): string {
  const label = EFFORT_LABELS[effort];

  return effort === support.value?.default_effort ? `${label} (default)` : label;
}

// Fields below the connection cover a missing key, so its note only shows on
// other connections and on a CLI that the server cannot find.
function methodNote(method: AuthMethodOption): string {
  if (method.ready) return '';

  if (method.id === form.authMethod && method.id !== 'cli') return '';

  return method.note;
}

function methodDescribedBy(method: AuthMethodOption): string {
  const summary = `${formId.value}-method-${method.id}`;

  return methodNote(method) ? `${summary} ${summary}-note` : summary;
}

const keyStored = computed(() => current.value?.api_key_configured ?? false);

const storedKeyText = computed(() => {
  const hint = current.value?.api_key_hint;

  return hint && hint !== 'set' ? `Key ${hint} is stored for this session.` : 'A key is stored for this session.';
});

const keyMissing = computed(() => form.authMethod === 'api_key' && !keyStored.value && !form.apiKey.trim());

const showKeyError = computed(() => touched.value && keyMissing.value);

const usesAccessKeys = computed(() => form.authMethod === 'bedrock' && form.bedrockCredentials === 'access_keys');

// Access keys are required unless a pair is already stored for this session.
const accessKeysStored = computed(() => props.config.anthropic_claude?.access_keys_configured ?? false);

const accessKeysMissing = computed(
  () =>
    usesAccessKeys.value && !accessKeysStored.value && (!form.accessKeyId.trim() || !form.secretAccessKey.trim()),
);

const showAccessKeysError = computed(() => touched.value && accessKeysMissing.value);

function describedBy(...ids: (string | false)[]): string | undefined {
  const present = ids.filter((id) => id !== false);

  return present.length > 0 ? present.join(' ') : undefined;
}

const isOverride = computed(() => current.value?.is_override ?? false);

// Send a secret only for the connection that uses it; a blank field keeps the stored value.
function typedSecret(value: string, used: boolean): string | null {
  return used ? value.trim() || null : null;
}

async function saveClaude(): Promise<boolean> {
  return store.saveAnthropicClaudeConfig({
    auth_method: form.authMethod,
    model_id: form.modelId,
    effort: form.effort,
    api_key: typedSecret(form.apiKey, form.authMethod === 'api_key'),
    bedrock_region: form.bedrockRegion.trim(),
    bedrock_credentials: form.bedrockCredentials,
    aws_profile: form.awsProfile.trim() || null,
    aws_access_key_id: typedSecret(form.accessKeyId, usesAccessKeys.value),
    aws_secret_access_key: typedSecret(form.secretAccessKey, usesAccessKeys.value),
    aws_session_token: typedSecret(form.sessionToken, usesAccessKeys.value),
  });
}

async function saveOpenAiGpt(): Promise<boolean> {
  const method = form.authMethod;

  // The GPT catalog never offers Bedrock, so the form cannot select it.
  if (method === 'bedrock') return false;

  return store.saveOpenAiGptConfig({
    auth_method: method,
    model_id: form.modelId,
    effort: form.effort,
    api_key: typedSecret(form.apiKey, method === 'api_key'),
  });
}

async function save(): Promise<void> {
  touched.value = true;

  if (keyMissing.value || accessKeysMissing.value || props.config.engine === 'offline') return;

  saving.value = true;

  const ok = props.config.engine === 'anthropic_claude' ? await saveClaude() : await saveOpenAiGpt();

  saving.value = false;

  if (!ok) return;

  notify('success', `${name.value} settings saved for this session.`);
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
      memory&nbsp;— never written to disk or logged&nbsp;— and cleared when the backend restarts.
    </p>

    <fieldset>
      <legend class="form-legend">Connection</legend>
      <div class="methods">
        <label
          v-for="method in config.auth_methods"
          :key="method.id"
          class="method"
          :class="{ 'is-selected': form.authMethod === method.id }"
        >
          <input
            v-model="form.authMethod"
            type="radio"
            :name="`${formId}-method`"
            :value="method.id"
            :aria-describedby="methodDescribedBy(method)"
          />
          <span class="method-text">
            <span class="method-label">{{ method.label }}</span>
            <span :id="`${formId}-method-${method.id}`" class="method-summary">{{ method.summary }}</span>
            <span
              v-if="methodNote(method)"
              :id="`${formId}-method-${method.id}-note`"
              class="method-note"
              :class="{ 'is-flag': form.authMethod === method.id }"
            >
              <TriangleAlert v-if="form.authMethod === method.id" :size="13" aria-hidden="true" />
              {{ methodNote(method) }}
            </span>
          </span>
        </label>
      </div>
    </fieldset>

    <dl v-if="form.authMethod === 'cli' && current" class="facts">
      <dt>Command</dt>
      <dd class="num">{{ current.command }}</dd>
    </dl>

    <div v-else-if="form.authMethod === 'api_key'" class="configure-fields">
      <div class="form-field">
        <label :for="`${formId}-api-key`">{{ chosenMethod?.label ?? 'API key' }}</label>
        <input
          :id="`${formId}-api-key`"
          v-model="form.apiKey"
          class="input"
          type="password"
          autocomplete="new-password"
          spellcheck="false"
          :aria-invalid="showKeyError"
          :aria-describedby="describedBy(`${formId}-api-key-hint`, showKeyError && `${formId}-api-key-error`)"
        />
        <p :id="`${formId}-api-key-hint`" class="hint num">
          {{
            keyStored
              ? `${storedKeyText} Leave blank to keep it.`
              : 'Write-only. The key stays in server memory and is never shown again.'
          }}
        </p>
        <p v-if="showKeyError" :id="`${formId}-api-key-error`" class="field-error" role="alert">
          <TriangleAlert :size="15" aria-hidden="true" />
          Enter an API key, or choose another connection.
        </p>
      </div>
    </div>

    <div v-else-if="form.authMethod === 'bedrock'" class="configure-fields">
      <div class="form-field">
        <label :for="`${formId}-region`">Region</label>
        <input
          :id="`${formId}-region`"
          v-model="form.bedrockRegion"
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

      <fieldset>
        <legend class="form-legend">AWS credentials</legend>
        <label class="choice">
          <input v-model="form.bedrockCredentials" type="radio" :name="`${formId}-credentials`" value="profile" />
          <span>AWS profile on this server</span>
        </label>
        <label class="choice">
          <input v-model="form.bedrockCredentials" type="radio" :name="`${formId}-credentials`" value="access_keys" />
          <span>Access keys for this session</span>
        </label>
      </fieldset>

      <div v-if="form.bedrockCredentials === 'profile'" class="form-field">
        <label :for="`${formId}-profile`">AWS profile name</label>
        <input
          :id="`${formId}-profile`"
          v-model="form.awsProfile"
          class="input"
          type="text"
          autocomplete="off"
          spellcheck="false"
          :aria-describedby="`${formId}-profile-hint`"
        />
        <p :id="`${formId}-profile-hint`" class="hint">
          Named profile from the server's AWS credentials file. Leave blank to use the default AWS credential chain.
        </p>
      </div>

      <template v-else>
        <div class="form-field">
          <label :for="`${formId}-key-id`">AWS access key ID</label>
          <input
            :id="`${formId}-key-id`"
            v-model="form.accessKeyId"
            class="input"
            type="text"
            autocomplete="off"
            spellcheck="false"
            :aria-invalid="showAccessKeysError"
            :aria-describedby="
              describedBy(accessKeysStored && `${formId}-keys-hint`, showAccessKeysError && `${formId}-keys-error`)
            "
          />
          <p v-if="accessKeysStored" :id="`${formId}-keys-hint`" class="hint num">
            Keys {{ config.anthropic_claude?.access_key_id_hint }} are stored for this session. Leave blank to keep
            them.
          </p>
        </div>

        <div class="form-field">
          <label :for="`${formId}-secret`">AWS secret access key</label>
          <input
            :id="`${formId}-secret`"
            v-model="form.secretAccessKey"
            class="input"
            type="password"
            autocomplete="new-password"
            :aria-invalid="showAccessKeysError"
            :aria-describedby="describedBy(showAccessKeysError && `${formId}-keys-error`)"
          />
        </div>

        <p v-if="showAccessKeysError" :id="`${formId}-keys-error`" class="field-error configure-wide" role="alert">
          <TriangleAlert :size="15" aria-hidden="true" />
          Access key ID and secret are required.
        </p>

        <div class="form-field">
          <label :for="`${formId}-token`">AWS session token (optional)</label>
          <input
            :id="`${formId}-token`"
            v-model="form.sessionToken"
            class="input"
            type="password"
            autocomplete="new-password"
            :aria-describedby="`${formId}-token-hint`"
          />
          <p :id="`${formId}-token-hint`" class="hint">Only needed for temporary STS credentials.</p>
        </div>
      </template>
    </div>

    <div class="configure-fields">
      <div class="form-field">
        <label :for="`${formId}-model`">Model</label>
        <select
          :id="`${formId}-model`"
          v-model="form.modelId"
          class="select"
          :aria-describedby="`${formId}-model-hint`"
        >
          <option v-for="model in modelsForMethod" :key="model.id" :value="model.id">{{ model.label }}</option>
        </select>
        <p :id="`${formId}-model-hint`" class="hint">
          {{ selectedModel?.summary }}
          <template v-if="support">
            Sent as <span class="num">{{ support.provider_model_id }}</span>.
          </template>
        </p>
      </div>

      <div class="form-field">
        <label :for="`${formId}-effort`">Reasoning effort</label>
        <select
          :id="`${formId}-effort`"
          v-model="form.effort"
          class="select"
          :disabled="efforts.length === 0"
          :aria-describedby="`${formId}-effort-hint`"
        >
          <option v-if="efforts.length === 0" :value="null">Not adjustable</option>
          <option v-for="effort in efforts" :key="effort" :value="effort">{{ effortOptionLabel(effort) }}</option>
        </select>
        <p :id="`${formId}-effort-hint`" class="hint">
          {{
            efforts.length > 0 ? effortHint(config.engine, form.authMethod) : 'This model takes no effort setting.'
          }}
        </p>
      </div>
    </div>

    <div class="configure-actions">
      <button type="submit" class="btn btn-primary" :disabled="saving || resetting">
        <LoaderCircle v-if="saving" :size="15" class="spin" aria-hidden="true" />
        <Save v-else :size="15" aria-hidden="true" />
        {{ saving ? 'Saving…' : 'Save for this session' }}
      </button>
      <button
        v-if="isOverride"
        type="button"
        class="btn btn-quiet"
        :disabled="saving || resetting"
        @click="resetToDefaults"
      >
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

/* Connection choices print as boxed fields that share their rules. */
.methods {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  margin-top: 0.3125rem;
  border-top: 1px solid var(--rule-strong);
  border-left: 1px solid var(--rule-strong);
}

.method {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  min-width: 0;
  padding: 0.5rem 0.625rem 0.625rem;
  border-right: 1px solid var(--rule-strong);
  border-bottom: 1px solid var(--rule-strong);
  background: var(--paper);
  cursor: pointer;
  transition:
    background-color var(--tint),
    box-shadow var(--tint);
}

.method:hover {
  background: var(--action-wash);
}

.method.is-selected {
  background: var(--action-wash);
  box-shadow: inset 0 0 0 1px var(--action);
}

.method input {
  flex: none;
  width: 1rem;
  height: 1rem;
  margin: 0.1875rem 0 0;
}

.method-text {
  display: grid;
  gap: 0.125rem;
  min-width: 0;
}

.method-label {
  font-weight: 600;
}

.method-summary {
  color: var(--ink-2);
  font-size: var(--text-small);
}

.method-note {
  display: flex;
  gap: 0.25rem;
  align-items: flex-start;
  margin-top: 0.125rem;
  color: var(--ink-3);
  font-size: var(--text-caption);
}

.method-note.is-flag {
  color: var(--flag-deep);
  font-weight: 600;
}

.method-note svg {
  flex: none;
  margin-top: 0.0625rem;
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

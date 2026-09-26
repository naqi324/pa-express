<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { ArrowLeft, CircleCheck, ClipboardCheck, List, LoaderCircle, Save, Send } from '@lucide/vue';
import { formatDate, formatDateTime, policyLabel } from '../format';
import { useAppStore } from '../store';
import { notify } from '../toast';
import AuditTrail from './AuditTrail.vue';
import CaseStatusChip from './CaseStatusChip.vue';

const store = useAppStore();

const { state } = store;

const request = computed(() => state.currentRequest);

const letter = computed(() => state.currentLetter);

const draftBody = ref('');

const loading = ref(false);

const saving = ref(false);

const sending = ref(false);

// referred_md is an internal handoff; no provider letter exists for it.
const referred = computed(() => request.value?.determination_status === 'referred_md');

const letterAvailable = computed(() => {
  const status = request.value?.determination_status;

  return status === 'approved' || status === 'pended';
});

const sent = computed(() => letter.value?.status === 'ready');

const dirty = computed(() => letter.value !== null && draftBody.value !== letter.value.body);

const letterTypeLabel = computed(() =>
  letter.value?.letter_type === 'approval' ? 'Approval letter' : 'Information request letter',
);

const authValidity = computed(() => {
  const current = request.value;

  if (!current?.auth_valid_from || !current.auth_valid_through) return null;

  return `${formatDate(current.auth_valid_from)} – ${formatDate(current.auth_valid_through)}`;
});

async function loadLetter(): Promise<void> {
  if (!letterAvailable.value) return;

  loading.value = true;
  await store.loadLetter();
  loading.value = false;
}

async function saveDraft(): Promise<void> {
  saving.value = true;

  const ok = await store.saveLetter(draftBody.value, false);

  saving.value = false;

  if (ok) notify('success', 'Draft saved. Your edits are in the audit trail.');
}

async function send(): Promise<void> {
  sending.value = true;

  const ok = await store.saveLetter(draftBody.value, true);

  sending.value = false;

  if (!ok) return;

  notify('success', 'Letter sent to the provider. The case is complete.');
  store.navigate('queue');
}

watch(
  letter,
  (next) => {
    if (next) draftBody.value = next.body;
  },
  { immediate: true },
);

onMounted(() => {
  if (!letter.value || letter.value.request_id !== request.value?.id) void loadLetter();
});
</script>

<template>
  <section v-if="request" class="page" aria-labelledby="letter-title">
    <div class="page-head">
      <div class="page-head-text">
        <h1 id="letter-title"><span class="num">{{ request.id }}</span> — {{ request.member.name }}</h1>
        <p class="muted">{{ request.service.description }}</p>
      </div>
      <div class="page-head-actions">
        <CaseStatusChip
          :processing="request.processing_status"
          :determination="request.determination_status"
          :notified="request.notified_at !== null"
        />
        <button type="button" class="btn btn-quiet" @click="store.navigate('workspace')">
          <ArrowLeft :size="15" aria-hidden="true" />
          Back to case
        </button>
        <button type="button" class="btn btn-quiet" @click="store.navigate('queue')">
          <List :size="15" aria-hidden="true" />
          Worklist
        </button>
      </div>
    </div>

    <div class="letter-layout">
      <section class="letter" aria-labelledby="letter-type-title">
        <header class="letter-head">
          <div>
            <h2 id="letter-type-title" class="letter-type">{{ letter ? letterTypeLabel : 'Provider letter' }}</h2>
            <p v-if="letter && !sent" class="muted">Review the provider-facing draft before sending.</p>
            <p v-else-if="letter && sent" class="muted num">
              Sent {{ request.notified_at ? formatDateTime(request.notified_at) : '' }} — the case is complete.
            </p>
          </div>
          <span v-if="letter" class="code" :class="{ 'code-action': !sent }">
            <CircleCheck v-if="sent" :size="13" aria-hidden="true" />
            <Save v-else :size="13" aria-hidden="true" />
            {{ sent ? 'Sent' : 'Draft' }}
          </span>
        </header>

        <div v-if="referred" class="absence">
          <h3>No provider letter for referrals</h3>
          <p>
            This case went to the Medical Director as an internal handoff — nothing is sent to the provider until the MD
            decides. Your summary is in the audit trail.
          </p>
          <div class="absence-actions">
            <button type="button" class="btn btn-primary" @click="store.navigate('queue')">
              <List :size="15" aria-hidden="true" />
              Back to worklist
            </button>
          </div>
        </div>

        <div v-else-if="!letterAvailable" class="absence">
          <h3>Dispose the case first</h3>
          <p>
            The letter is drafted from your disposition — approve or request information in the case workspace and it
            appears here, ready to review and send.
          </p>
          <div class="absence-actions">
            <button type="button" class="btn btn-primary" @click="store.navigate('workspace')">
              <ArrowLeft :size="15" aria-hidden="true" />
              Go to case workspace
            </button>
          </div>
        </div>

        <div v-else-if="loading && !letter" class="letter-skeleton" aria-busy="true" aria-label="Loading letter">
          <span class="skeleton-bar" style="width: 55%" />
          <span class="skeleton-bar" style="width: 35%" />
          <span class="skeleton-sheet" />
        </div>

        <template v-else-if="letter">
          <p v-if="!sent" class="notice notice-action" role="note">
            <ClipboardCheck :size="16" aria-hidden="true" />
            <span class="notice-body">
              Drafted from the criterion-level determination. You own the content before it goes out.
            </span>
          </p>

          <dl class="facts">
            <dt>Subject</dt>
            <dd>{{ letter.subject }}</dd>
            <dt>Policy basis</dt>
            <dd>{{ policyLabel(request.policy) }}</dd>
            <template v-if="letter.letter_type === 'approval' && authValidity">
              <dt>Authorization valid</dt>
              <dd class="num">{{ authValidity }}</dd>
            </template>
          </dl>

          <div class="form-field">
            <label for="letter-body">{{ sent ? 'Letter body (sent — read only)' : 'Letter body' }}</label>
            <textarea
              id="letter-body"
              v-model="draftBody"
              class="textarea sheet"
              :readonly="sent"
              :aria-describedby="sent ? undefined : 'letter-lock-hint'"
              spellcheck="true"
            />
            <p v-if="!sent" id="letter-lock-hint" class="hint">Sending locks the letter. It cannot be edited after it goes out.</p>
          </div>

          <div v-if="!sent" class="letter-actions">
            <button type="button" class="btn btn-primary" :disabled="sending || saving" @click="send">
              <LoaderCircle v-if="sending" :size="15" class="spin" aria-hidden="true" />
              <Send v-else :size="15" aria-hidden="true" />
              {{ sending ? 'Sending…' : 'Send to provider' }}
            </button>
            <button type="button" class="btn" :disabled="saving || sending || !dirty" @click="saveDraft">
              <LoaderCircle v-if="saving" :size="15" class="spin" aria-hidden="true" />
              <Save v-else :size="15" aria-hidden="true" />
              {{ saving ? 'Saving…' : 'Save draft' }}
            </button>
          </div>
          <div v-else class="letter-actions">
            <button type="button" class="btn btn-primary" @click="store.navigate('queue')">
              <List :size="15" aria-hidden="true" />
              Back to worklist
            </button>
          </div>
        </template>
      </section>

      <section class="trail" aria-labelledby="letter-audit-title">
        <div class="trail-head">
          <h2 id="letter-audit-title" class="section-title">Audit trail</h2>
          <p class="muted">Every state transition with actor and timestamp.</p>
        </div>
        <AuditTrail :events="request.audit_trail" />
      </section>
    </div>
  </section>

  <section v-else class="page" aria-labelledby="no-letter-case-title">
    <div class="absence">
      <h1 id="no-letter-case-title" class="no-case-title">No case selected</h1>
      <p>Open a case from the worklist, dispose it, then return here for the letter and audit trail.</p>
      <div class="absence-actions">
        <button type="button" class="btn btn-primary" @click="store.navigate('queue')">
          <List :size="15" aria-hidden="true" />
          Go to worklist
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.letter-layout {
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(0, 5fr);
  gap: var(--space-5);
  align-items: start;
}

.letter {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5) var(--space-5);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
}

.letter-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--rule);
}

.letter-type {
  font-size: var(--text-h3);
}

.letter-head .muted {
  font-size: var(--text-small);
}

.sheet {
  min-height: 26rem;
  padding: var(--space-4) var(--space-5);
  font-size: var(--text-body);
  line-height: 1.65;
}

.sheet:read-only {
  background: var(--surface);
  color: var(--ink);
}

.letter-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--rule);
}

.letter-skeleton {
  display: grid;
  gap: var(--space-3);
}

.skeleton-sheet {
  display: block;
  height: 20rem;
  border: 1px dashed var(--rule-strong);
  border-radius: var(--radius);
  background: var(--surface);
}

.trail {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
}

.trail-head {
  display: grid;
  gap: var(--space-1);
}

.trail-head .muted {
  font-size: var(--text-small);
}

.no-case-title {
  font-size: var(--text-h2);
}

@media (max-width: 64rem) {
  .letter-layout {
    grid-template-columns: 1fr;
  }
}
</style>

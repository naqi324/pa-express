<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import {
  CircleAlert,
  CircleCheck,
  CirclePause,
  FileQuestionMark,
  Info,
  Send,
  Signature,
  Stethoscope,
} from '@lucide/vue';
import type { Determination, HumanActionRequest, PARequest } from '../types';

// The sign-off column: recommendation, criteria count, and the three
// dispositions. Each disposition opens its form inline, never in a dialog.
const props = defineProps<{
  determination: Determination;
  request: PARequest;
  busy: boolean;
}>();

const emit = defineEmits<{
  disposed: [payload: Omit<HumanActionRequest, 'actor'>];
}>();

type SignOff = 'approve' | 'pend' | 'refer';

interface PendItem {
  id: string;
  label: string;
  checked: boolean;
}

const VALIDITY_DAYS = 90;

const NOTE_LIMIT = 500;

const SUMMARY_LIMIT = 1000;

const isApprove = computed(() => props.determination.recommendation === 'approve');

const disposed = computed(() => props.request.determination_status !== 'in_review');

const open = ref<SignOff | null>(null);

const formHeading = ref<HTMLHeadingElement | null>(null);

const approveNote = ref('');

const validFrom = ref('');

const validThrough = ref('');

const pendNote = ref('');

const pendItems = ref<PendItem[]>([]);

const referSummary = ref('');

// Local calendar date as yyyy-mm-dd, the value format of a date input.
function localIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');

  return `${date.getFullYear()}-${month}-${day}`;
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);

  next.setDate(next.getDate() + days);

  return next;
}

// The items the provider must send, pre-checked from the unmet or
// insufficient criteria and the engine's documentation gaps. Gaps often
// restate a criterion verbatim, so both lists dedupe on the raw text.
function buildPendItems(): PendItem[] {
  const items: PendItem[] = [];
  const seen = new Set<string>();

  for (const criterion of props.determination.criteria_evaluations) {
    if (criterion.status === 'MET' || seen.has(criterion.criterion_text)) continue;

    seen.add(criterion.criterion_text);
    items.push({
      id: `criterion-${criterion.criterion_id}`,
      label: `Documentation demonstrating: ${criterion.criterion_text}`,
      checked: true,
    });
  }

  for (const [index, gap] of props.determination.gaps.entries()) {
    if (seen.has(gap)) continue;

    seen.add(gap);
    items.push({ id: `gap-${index}`, label: gap, checked: true });
  }

  return items;
}

const selectedPendItems = computed(() => pendItems.value.flatMap((item) => (item.checked ? [item.label] : [])));

const pendInvalid = computed(() => selectedPendItems.value.length === 0);

const pendButtonLabel = computed(() => {
  const count = selectedPendItems.value.length;

  return `Request ${count} item${count === 1 ? '' : 's'}`;
});

const referEmpty = computed(() => referSummary.value.trim().length === 0);

async function start(signOff: SignOff): Promise<void> {
  if (open.value === signOff) {
    open.value = null;

    return;
  }

  if (signOff === 'approve') {
    const today = new Date();

    approveNote.value = '';
    validFrom.value = localIsoDate(today);
    validThrough.value = localIsoDate(addDays(today, VALIDITY_DAYS));
  } else if (signOff === 'pend') {
    pendNote.value = '';
    pendItems.value = buildPendItems();
  } else {
    referSummary.value = '';
  }

  open.value = signOff;
  await nextTick();
  formHeading.value?.focus();
}

function cancel(): void {
  open.value = null;
}

function confirmApprove(): void {
  emit('disposed', {
    action: 'approve',
    note: approveNote.value.trim(),
    valid_from: validFrom.value || null,
    valid_through: validThrough.value || null,
  });
  open.value = null;
}

function confirmPend(): void {
  if (pendInvalid.value) return;

  emit('disposed', {
    action: 'pend',
    note: pendNote.value.trim(),
    requested_items: selectedPendItems.value,
  });
  open.value = null;
}

function confirmRefer(): void {
  const summary = referSummary.value.trim();

  if (!summary) return;

  emit('disposed', { action: 'refer_md', note: summary });
  open.value = null;
}
</script>

<template>
  <section class="signoff" aria-labelledby="signoff-title">
    <div class="verdict">
      <h2 id="signoff-title" class="verdict-title">
        <CircleCheck v-if="isApprove" :size="20" class="verdict-icon" aria-hidden="true" />
        <FileQuestionMark v-else :size="20" class="verdict-icon verdict-icon-flag" aria-hidden="true" />
        <span class="visually-hidden">{{ isApprove ? 'Recommendation: approve.' : 'Recommendation: request information.' }}</span>
        {{ isApprove ? 'Meets criteria — recommend approval' : 'Documentation incomplete — recommend requesting information' }}
      </h2>
      <p class="verdict-count num">{{ determination.criteria_met }}</p>
      <p class="verdict-rationale">{{ determination.rationale }}</p>
      <p class="verdict-source caption">Recommendation source: {{ determination.attribution.engine_label }}</p>
    </div>

    <div v-if="disposed" class="disposed" role="status">
      <template v-if="request.determination_status === 'approved'">
        <CircleCheck :size="18" aria-hidden="true" />
        <span>Approved</span>
      </template>
      <template v-else-if="request.determination_status === 'pended'">
        <CirclePause :size="18" aria-hidden="true" />
        <span>Pended — information requested</span>
      </template>
      <template v-else>
        <Stethoscope :size="18" aria-hidden="true" />
        <span>Referred to Medical Director</span>
      </template>
    </div>

    <template v-else>
      <div class="signoff-actions" role="group" aria-label="Disposition">
        <button
          type="button"
          class="btn btn-block"
          :class="{ 'btn-primary': isApprove && open !== 'approve', 'is-open': open === 'approve' }"
          :aria-expanded="open === 'approve'"
          aria-controls="signoff-form"
          :disabled="busy"
          @click="start('approve')"
        >
          <Signature :size="16" aria-hidden="true" />
          Approve
        </button>
        <button
          type="button"
          class="btn btn-block"
          :class="{ 'btn-primary': !isApprove && open !== 'pend', 'is-open': open === 'pend' }"
          :aria-expanded="open === 'pend'"
          aria-controls="signoff-form"
          :disabled="busy"
          @click="start('pend')"
        >
          <Send :size="16" aria-hidden="true" />
          Request information
        </button>
        <button
          type="button"
          class="btn btn-block"
          :class="{ 'is-open': open === 'refer' }"
          :aria-expanded="open === 'refer'"
          aria-controls="signoff-form"
          :disabled="busy"
          @click="start('refer')"
        >
          <Stethoscope :size="16" aria-hidden="true" />
          Refer to MD
        </button>
      </div>

      <div id="signoff-form">
        <form v-if="open === 'approve'" class="signoff-form" @submit.prevent="confirmApprove">
          <h3 ref="formHeading" tabindex="-1" class="form-title">Approve this request?</h3>
          <p class="form-lead">
            Approving <strong>{{ request.service.description }}</strong> for
            <strong>{{ request.member.name }}</strong> — {{ determination.criteria_met }}. An approval letter with the
            authorization number and validity window will be drafted for your review.
          </p>
          <div class="date-pair">
            <div class="form-field">
              <label for="valid-from">Valid from</label>
              <input id="valid-from" v-model="validFrom" type="date" class="input" required />
            </div>
            <div class="form-field">
              <label for="valid-through">Valid through</label>
              <input id="valid-through" v-model="validThrough" type="date" class="input" :min="validFrom" required />
            </div>
          </div>
          <div class="form-field">
            <label for="approve-note">Reviewer note (optional)</label>
            <textarea
              id="approve-note"
              v-model="approveNote"
              class="textarea"
              rows="2"
              :maxlength="NOTE_LIMIT"
              placeholder="Context for the audit trail"
            />
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary" :disabled="busy">Approve</button>
            <button type="button" class="btn btn-quiet" @click="cancel">Cancel</button>
          </div>
        </form>

        <form v-else-if="open === 'pend'" class="signoff-form" @submit.prevent="confirmPend">
          <h3 ref="formHeading" tabindex="-1" class="form-title">Request information from the provider</h3>
          <p class="form-lead">
            The case pends — not a denial — while the provider supplies the items below. Uncheck anything you don't
            need; the request letter lists exactly what you select.
          </p>
          <fieldset class="pend-items" aria-label="Information to request" :aria-describedby="pendInvalid ? 'pend-error' : undefined">
            <label v-for="item in pendItems" :key="item.id" class="choice">
              <input v-model="item.checked" type="checkbox" />
              <span>{{ item.label }}</span>
            </label>
          </fieldset>
          <p v-if="pendInvalid" id="pend-error" class="field-error" role="alert">
            <CircleAlert :size="15" aria-hidden="true" />
            Select at least one item — the provider needs to know exactly what to send.
          </p>
          <div class="form-field">
            <label for="pend-note">Reviewer note (optional)</label>
            <textarea
              id="pend-note"
              v-model="pendNote"
              class="textarea"
              rows="2"
              :maxlength="NOTE_LIMIT"
              placeholder="Context for the audit trail"
            />
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary num" :disabled="busy || pendInvalid">{{ pendButtonLabel }}</button>
            <button type="button" class="btn btn-quiet" @click="cancel">Cancel</button>
          </div>
        </form>

        <form v-else-if="open === 'refer'" class="signoff-form" @submit.prevent="confirmRefer">
          <h3 ref="formHeading" tabindex="-1" class="form-title">Refer to Medical Director</h3>
          <p class="form-lead">
            An internal handoff — no provider letter is sent. Summarize the case and what you want the Medical Director
            to weigh in on.
          </p>
          <div class="form-field">
            <label for="refer-summary">Summary for the Medical Director (required)</label>
            <textarea
              id="refer-summary"
              v-model="referSummary"
              class="textarea"
              rows="4"
              :maxlength="SUMMARY_LIMIT"
              required
              placeholder="Clinical picture, which criteria are in question, and your recommendation"
            />
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary" :disabled="busy || referEmpty">Refer case</button>
            <button type="button" class="btn btn-quiet" @click="cancel">Cancel</button>
          </div>
        </form>
      </div>

      <p class="never-deny">
        <Info :size="14" aria-hidden="true" />
        Approve or pend only — potential denials go to the Medical Director (CMS-4201-F).
      </p>
    </template>
  </section>
</template>

<style scoped>
.signoff {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
}

.verdict {
  display: grid;
  gap: var(--space-2);
}

.verdict-title {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  font-size: var(--text-lead);
  line-height: 1.3;
}

.verdict-icon {
  flex: none;
  margin-top: 0.0625rem;
  color: var(--ink);
}

.verdict-icon-flag {
  color: var(--flag);
}

.verdict-count {
  font-weight: 700;
}

.verdict-rationale {
  color: var(--ink-2);
  font-size: var(--text-small);
}

.disposed {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--sunk);
  font-weight: 700;
}

.signoff-actions {
  display: grid;
  gap: var(--space-2);
}

.btn.is-open {
  background: var(--action-wash-2);
  border-color: var(--action);
  color: var(--ink);
}

.signoff-form {
  display: grid;
  gap: var(--space-3);
  padding-top: var(--space-4);
  border-top: 1px solid var(--rule);
  animation: form-in 180ms var(--ease-out);
}

.form-title {
  font-size: var(--text-body);
}

.form-title:focus-visible {
  outline-offset: 3px;
}

.form-lead {
  color: var(--ink-2);
  font-size: var(--text-small);
}

.form-lead strong {
  color: var(--ink);
}

.date-pair {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: var(--space-3);
}

.pend-items {
  display: grid;
  max-height: 16rem;
  overflow-y: auto;
  padding: 0.25rem 0.625rem;
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  background: var(--surface);
  font-size: var(--text-small);
}

.pend-items .choice + .choice {
  border-top: 1px solid var(--rule);
}

.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.never-deny {
  display: flex;
  gap: 0.375rem;
  align-items: flex-start;
  padding-top: var(--space-3);
  border-top: 1px solid var(--rule);
  color: var(--ink-3);
  font-size: var(--text-caption);
  font-weight: 600;
}

.never-deny svg {
  flex: none;
  margin-top: 0.0625rem;
}

@keyframes form-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
}
</style>

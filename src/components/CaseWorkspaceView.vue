<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import {
  ArrowLeft,
  CircleCheck,
  ExternalLink,
  FileText,
  Info,
  List,
  LoaderCircle,
  Lock,
  MailCheck,
  PenLine,
  RotateCw,
  TriangleAlert,
} from '@lucide/vue';
import { docTypeLabel, markedParts } from '../documentText';
import { formatDate, formatDateTime, formatStamp, planTypeLabel, policyId, policyLabel } from '../format';
import { useAppStore } from '../store';
import { useScrollFade } from '../scrollFade';
import { notify } from '../toast';
import type { AuditEvent, ClinicalDocument, HumanActionRequest } from '../types';
import AuditTrail from './AuditTrail.vue';
import CaseStatusChip from './CaseStatusChip.vue';
import CriteriaGrid from './CriteriaGrid.vue';
import DeterminationPanel from './DeterminationPanel.vue';
import LlmInspector from './LlmInspector.vue';
import PolicyViewer from './PolicyViewer.vue';
import SlaCountdown from './SlaCountdown.vue';

type TabId = 'criteria' | 'submission' | 'decision';

interface LifecycleStep {
  label: string;
  value: string;
  done: boolean;
  flag: boolean;
}

const store = useAppStore();

const { state } = store;

// Tabs follow the reviewer's jobs: check the criteria against the record,
// read the full submission, then trace the decision.
const TABS: { id: TabId; label: string }[] = [
  { id: 'criteria', label: 'Criteria & evidence' },
  { id: 'submission', label: 'Submission' },
  { id: 'decision', label: 'Decision & audit' },
];

const activeTab = ref<TabId>('criteria');

const tabStrip = ref<HTMLElement | null>(null);

useScrollFade(tabStrip, () => activeTab.value);

const disposing = ref(false);

const policyOpen = ref(false);

// The passages to mark in one submitted document, set by an evidence jump.
const highlight = ref<{ docId: string; quotes: string[] } | null>(null);

const request = computed(() => state.currentRequest);

const determination = computed(() => state.currentDetermination);

const analyzing = computed(() => {
  const status = request.value?.processing_status;

  return status === 'queued' || status === 'analyzing';
});

const failed = computed(() => request.value?.processing_status === 'failed');

const disposed = computed(() => request.value !== null && request.value.determination_status !== 'in_review');

const letterAvailable = computed(() => {
  const status = request.value?.determination_status;

  return status === 'approved' || status === 'pended';
});

const policy = computed(() => request.value?.policy ?? null);

const isNcd = computed(() => policy.value?.source_type === 'ncd');

const coverage = computed(() => determination.value?.coverage_check ?? null);

const attribution = computed(() => determination.value?.attribution ?? null);

const modelLabel = computed(() => attribution.value?.model_id ?? 'Deterministic (no LLM)');

const cmsLinkLabel = computed(() => {
  const current = policy.value;

  if (!current) return '';

  return current.source_type === 'ncd'
    ? `Open NCD ${current.ncd_id ?? current.code} on cms.gov`
    : `Open LCD ${current.lcd_id ?? current.code} on cms.gov`;
});

const urgencyFact = computed(() =>
  request.value?.service.urgency === 'expedited' ? 'Expedited — 72-hour decision' : 'Standard — 7-day decision',
);

const settingFact = computed(() => {
  const setting = request.value?.service.setting ?? '';

  return setting.charAt(0).toUpperCase() + setting.slice(1);
});

const codesLine = computed(() => {
  const service = request.value?.service;

  if (!service) return '';

  return [...service.cpt_codes.map((code) => `CPT ${code}`), ...service.icd10_codes.map((code) => `ICD-10 ${code}`)].join(
    ' · ',
  );
});

const dispositionTitle = computed(() => {
  const status = request.value?.determination_status;

  if (status === 'approved') return 'Approved';

  if (status === 'pended') return 'Information requested';

  if (status === 'referred_md') return 'Referred to Medical Director';

  return '';
});

const authValidity = computed(() => {
  const current = request.value;

  if (!current?.auth_valid_from || !current.auth_valid_through) return null;

  return `${formatDate(current.auth_valid_from)} – ${formatDate(current.auth_valid_through)}`;
});

function lastEvent(events: AuditEvent[], matches: (event: string) => boolean): AuditEvent | null {
  return events.findLast((entry) => matches(entry.event)) ?? null;
}

// The reviewer's own sign-off, read from the audit trail. Null until the
// reviewer disposes the case; after that the disposition cannot change.
const signature = computed(() => {
  const current = request.value;

  if (!current || current.determination_status === 'in_review') return null;

  return lastEvent(current.audit_trail, (event) => event.startsWith('human_action_'));
});

const letterStatus = computed(() => {
  const current = request.value;

  if (!current || !signature.value) return '—';

  if (current.notified_at) return `Sent ${formatStamp(current.notified_at)}`;

  if (current.determination_status === 'referred_md') return 'None — internal handoff';

  return 'Drafted, not sent';
});

// One row of stamps from intake to letter, read from the audit trail.
const lifecycle = computed<LifecycleStep[]>(() => {
  const current = request.value;

  if (!current) return [];

  const events = current.audit_trail;
  const started = lastEvent(events, (event) => event === 'evaluation_started');
  const finished = lastEvent(events, (event) => event === 'evaluation_completed' || event === 'evaluation_failed');
  const decided = lastEvent(events, (event) => event.startsWith('human_action_'));
  const analysisFailed = finished?.event === 'evaluation_failed';
  const referred = current.determination_status === 'referred_md';

  let letter = '—';

  if (current.notified_at) letter = formatStamp(current.notified_at);
  else if (referred) letter = 'Not sent — internal handoff';
  else if (letterAvailable.value) letter = 'Drafted, not sent';

  return [
    { label: 'Received', value: formatStamp(current.created_at), done: true, flag: false },
    { label: 'Analysis started', value: started ? formatStamp(started.timestamp) : '—', done: started !== null, flag: false },
    {
      label: analysisFailed ? 'Analysis failed' : 'Analysis completed',
      value: finished ? formatStamp(finished.timestamp) : '—',
      done: finished !== null,
      flag: analysisFailed,
    },
    {
      label: decided ? `Decided — ${dispositionTitle.value}` : 'Decision',
      value: decided ? formatStamp(decided.timestamp) : finished ? 'Awaiting reviewer' : '—',
      done: decided !== null,
      flag: false,
    },
    {
      label: current.notified_at ? 'Letter sent' : 'Provider letter',
      value: letter,
      done: current.notified_at !== null || referred,
      flag: false,
    },
  ];
});

const nextStep = computed(() => lifecycle.value.findIndex((step) => !step.done));

function documentParts(doc: ClinicalDocument): { text: string; mark: boolean }[] {
  const active = highlight.value;

  return markedParts(doc.text, active?.docId === doc.id ? active.quotes : []);
}

function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function selectTab(tab: TabId): void {
  activeTab.value = tab;
}

function onTabKeydown(event: KeyboardEvent): void {
  const index = TABS.findIndex((tab) => tab.id === activeTab.value);
  let next = -1;

  if (event.key === 'ArrowRight') next = (index + 1) % TABS.length;
  else if (event.key === 'ArrowLeft') next = (index - 1 + TABS.length) % TABS.length;
  else if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = TABS.length - 1;

  const target = TABS[next];

  if (!target) return;

  event.preventDefault();
  selectTab(target.id);
  document.getElementById(`tab-${target.id}`)?.focus();
}

// Show a submitted document in full on the Submission tab, with the quoted
// passages marked, and move focus there so keyboard users land on it.
async function showDocument(docId: string, quotes: string[]): Promise<void> {
  highlight.value = quotes.length > 0 ? { docId, quotes } : null;
  selectTab('submission');
  await nextTick();

  const article = document.getElementById(`doc-${docId}`);

  article?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
  article?.focus({ preventScroll: true });
}

async function showPolicy(): Promise<void> {
  policyOpen.value = true;
  selectTab('submission');
  await nextTick();
  document.getElementById('policy-basis')?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
}

async function rerun(): Promise<void> {
  await store.runEvaluation();
}

async function onDisposed(payload: Omit<HumanActionRequest, 'actor'>): Promise<void> {
  disposing.value = true;

  const ok = await store.submitAction({ ...payload, actor: 'UM Reviewer' });

  disposing.value = false;

  if (!ok) return;

  if (payload.action === 'refer_md') {
    notify('success', 'Case referred to the Medical Director with your summary.');
    store.navigate('queue');
  } else {
    store.navigate('letter-audit');
  }
}

// A different case always opens on its criteria.
watch(
  () => request.value?.id,
  () => {
    activeTab.value = 'criteria';
    highlight.value = null;
    policyOpen.value = false;
  },
);
</script>

<template>
  <section v-if="request" class="page workspace" aria-labelledby="case-title">
    <div class="page-head">
      <div class="page-head-text">
        <h1 id="case-title"><span class="num">{{ request.id }}</span> — {{ request.member.name }}</h1>
        <p class="muted">{{ request.service.description }}</p>
      </div>
      <div class="page-head-actions">
        <CaseStatusChip
          :processing="request.processing_status"
          :determination="request.determination_status"
          :notified="request.notified_at !== null"
        />
        <button type="button" class="btn btn-quiet" @click="store.navigate('queue')">
          <ArrowLeft :size="15" aria-hidden="true" />
          Back to worklist
        </button>
        <button v-if="letterAvailable" type="button" class="btn" @click="store.navigate('letter-audit')">
          <MailCheck :size="15" aria-hidden="true" />
          Provider letter
        </button>
      </div>
    </div>

    <dl class="boxes banner" aria-label="Case summary">
      <div class="box">
        <dt class="caption">Member ID</dt>
        <dd class="box-value num">{{ request.member.member_id }}</dd>
      </div>
      <div class="box">
        <dt class="caption">Date of birth</dt>
        <dd class="box-value num">{{ formatDate(request.member.date_of_birth) }}</dd>
      </div>
      <div class="box">
        <dt class="caption">Plan</dt>
        <dd class="box-value">{{ request.member.plan_name }} · {{ planTypeLabel(request.member.plan_type) }}</dd>
      </div>
      <div class="box">
        <dt class="caption">Requesting provider</dt>
        <dd class="box-value">{{ request.provider.name }} · <span class="num">NPI {{ request.provider.npi }}</span></dd>
      </div>
      <div class="box">
        <dt class="caption">Service codes</dt>
        <dd class="box-value num">{{ codesLine }}</dd>
      </div>
      <div class="box">
        <dt class="caption">Setting</dt>
        <dd class="box-value">{{ settingFact }}</dd>
      </div>
      <div class="box">
        <dt class="caption">Urgency</dt>
        <dd class="box-value" :class="{ 'value-flag': request.service.urgency === 'expedited' }">
          {{ request.service.urgency === 'expedited' ? 'Expedited' : 'Standard' }}
        </dd>
      </div>
      <div class="box box-due">
        <dt class="caption">Decision due</dt>
        <dd class="box-value num">{{ formatStamp(request.sla_due_at) }}</dd>
        <dd v-if="!disposed" class="due-countdown">
          <SlaCountdown :due-at="request.sla_due_at" :expedited="request.service.urgency === 'expedited'" />
        </dd>
        <dd v-else class="due-countdown muted">Decided</dd>
      </div>
    </dl>

    <ol class="lifecycle" aria-label="Case progress">
      <li
        v-for="(step, index) in lifecycle"
        :key="step.label"
        class="stamp"
        :class="{ 'is-done': step.done, 'is-next': index === nextStep, 'is-flag': step.flag }"
        :aria-current="index === nextStep ? 'step' : undefined"
      >
        <span class="stamp-label caption">{{ step.label }}</span>
        <span class="stamp-value num">{{ step.value }}</span>
      </li>
    </ol>

    <div v-if="state.evaluationNotice" class="notice notice-flag" role="status">
      <TriangleAlert :size="16" aria-hidden="true" />
      <p class="notice-body">{{ state.evaluationNotice }}</p>
    </div>

    <div class="workspace-layout">
      <aside class="decision" aria-label="Decision">
        <div v-if="analyzing" class="decision-status" role="status" aria-live="polite">
          <LoaderCircle :size="18" class="spin" aria-hidden="true" />
          <div>
            <p class="decision-status-title">
              Analyzing clinical documentation against {{ request.policy?.code ?? 'policy' }} criteria…
            </p>
            <p class="decision-status-copy">
              Read the record while the analysis runs. The recommendation and sign-off actions appear here when it
              completes.
            </p>
          </div>
        </div>

        <div v-else-if="failed" class="decision-status decision-status-flag" role="alert">
          <TriangleAlert :size="18" aria-hidden="true" />
          <div>
            <p class="decision-status-title">The automated analysis failed for this case.</p>
            <button type="button" class="btn btn-primary" :disabled="state.evaluating" @click="rerun">
              <LoaderCircle v-if="state.evaluating" :size="15" class="spin" aria-hidden="true" />
              <RotateCw v-else :size="15" aria-hidden="true" />
              {{ state.evaluating ? 'Retrying analysis…' : 'Retry analysis' }}
            </button>
          </div>
        </div>

        <DeterminationPanel
          v-else-if="determination"
          :determination="determination"
          :request="request"
          :busy="disposing || state.evaluating"
          @disposed="onDisposed"
        />

        <section
          v-if="determination && determination.gaps.length > 0 && !disposed"
          class="gaps"
          aria-labelledby="gaps-title"
        >
          <h2 id="gaps-title" class="gaps-title">Documentation gaps</h2>
          <ul class="gaps-list">
            <li v-for="(gap, index) in determination.gaps" :key="index">{{ gap }}</li>
          </ul>
        </section>
      </aside>

      <div class="workspace-main">
        <div ref="tabStrip" class="divider-tabs" role="tablist" aria-label="Case sections" @keydown="onTabKeydown">
          <button
            v-for="tab in TABS"
            :id="`tab-${tab.id}`"
            :key="tab.id"
            type="button"
            role="tab"
            class="divider-tab"
            :aria-selected="activeTab === tab.id"
            :aria-controls="`panel-${tab.id}`"
            :tabindex="activeTab === tab.id ? 0 : -1"
            @click="selectTab(tab.id)"
          >
            {{ tab.label }}
            <span v-if="tab.id === 'submission'" class="tab-count">{{ request.clinical_documents.length }}</span>
          </button>
        </div>

        <div
          v-if="activeTab === 'criteria'"
          id="panel-criteria"
          role="tabpanel"
          aria-labelledby="tab-criteria"
          class="tab-panel"
        >
          <CriteriaGrid
            :request="request"
            :determination="determination"
            :analyzing="analyzing"
            @show-document="showDocument"
            @show-policy="showPolicy"
          />
        </div>

        <div
          v-else-if="activeTab === 'submission'"
          id="panel-submission"
          role="tabpanel"
          aria-labelledby="tab-submission"
          class="tab-panel"
        >
          <section class="block" aria-labelledby="request-facts-title">
            <h2 id="request-facts-title" class="block-title">Request</h2>
            <dl class="facts">
              <dt>Received</dt>
              <dd class="num">{{ formatDateTime(request.created_at) }}</dd>
              <dt>Urgency</dt>
              <dd>{{ urgencyFact }}</dd>
              <dt>Setting</dt>
              <dd>{{ settingFact }}</dd>
              <dt>Decision due</dt>
              <dd class="num">{{ formatDateTime(request.sla_due_at) }}</dd>
            </dl>
          </section>

          <div class="block-pair">
            <section class="block" aria-labelledby="member-facts-title">
              <h2 id="member-facts-title" class="block-title">Member</h2>
              <dl class="facts">
                <dt>Name</dt>
                <dd>{{ request.member.name }}</dd>
                <dt>Member ID</dt>
                <dd class="num">{{ request.member.member_id }}</dd>
                <dt>Date of birth</dt>
                <dd class="num">{{ formatDate(request.member.date_of_birth) }}</dd>
                <dt>Plan</dt>
                <dd>{{ request.member.plan_name }} ({{ planTypeLabel(request.member.plan_type) }})</dd>
              </dl>
            </section>
            <section class="block" aria-labelledby="provider-facts-title">
              <h2 id="provider-facts-title" class="block-title">Requesting provider</h2>
              <dl class="facts">
                <dt>Name</dt>
                <dd>{{ request.provider.name }}</dd>
                <dt>NPI</dt>
                <dd class="num">{{ request.provider.npi }}</dd>
                <dt>Specialty</dt>
                <dd>{{ request.provider.specialty }}</dd>
                <dt>Organization</dt>
                <dd>{{ request.provider.organization }}</dd>
              </dl>
            </section>
          </div>

          <section class="block" aria-labelledby="records-title">
            <div class="block-head">
              <h2 id="records-title" class="block-title">
                Submitted records <span class="tab-count">{{ request.clinical_documents.length }}</span>
              </h2>
              <p class="block-lead">
                Everything submitted on the member's behalf, in full. Evidence quotes on the Criteria &amp; evidence tab
                link back to the highlighted passage here.
              </p>
            </div>
            <article
              v-for="doc in request.clinical_documents"
              :id="`doc-${doc.id}`"
              :key="doc.id"
              class="record"
              tabindex="-1"
              :aria-labelledby="`doc-title-${doc.id}`"
            >
              <header class="record-head">
                <h3 :id="`doc-title-${doc.id}`" class="record-title">{{ doc.title }}</h3>
                <span class="caption">{{ docTypeLabel(doc.doc_type) }} · <span class="num">{{ formatDate(doc.date) }}</span></span>
              </header>
              <div class="record-text"><template v-for="(part, index) in documentParts(doc)" :key="index"><mark v-if="part.mark">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></div>
            </article>
            <p v-if="request.clinical_documents.length === 0" class="absence">
              No clinical documentation was submitted with this request.
            </p>
          </section>

          <section v-if="policy" id="policy-basis" class="block" aria-labelledby="policy-basis-title">
            <div class="block-head">
              <h2 id="policy-basis-title" class="block-title">Policy basis</h2>
              <p class="block-lead">The CMS coverage policy this request is evaluated against.</p>
            </div>
            <dl class="facts">
              <dt>Source</dt>
              <dd>{{ isNcd ? 'CMS National Coverage Determination' : 'CMS Local Coverage Determination' }}</dd>
              <dt>Reference</dt>
              <dd>{{ policy.code }} — {{ policy.title }}</dd>
              <template v-if="policy.version">
                <dt>Version</dt>
                <dd class="num">{{ policy.version }}</dd>
              </template>
              <template v-if="!isNcd && policy.contractor">
                <dt>Contractor</dt>
                <dd>{{ policy.contractor }}</dd>
              </template>
              <template v-if="coverage">
                <dt>Coverage</dt>
                <dd class="coverage-fact" :class="{ 'value-flag': !coverage.covered }">
                  <CircleCheck v-if="coverage.covered" :size="15" aria-hidden="true" />
                  <TriangleAlert v-else :size="15" aria-hidden="true" />
                  {{ coverage.covered ? 'Covered — coverage criteria confirmed below' : 'Coverage criteria review required' }}
                </dd>
              </template>
            </dl>
            <p v-if="coverage" class="block-lead">{{ coverage.summary }}</p>
            <div class="block-actions">
              <button
                type="button"
                class="btn"
                :aria-expanded="policyOpen"
                aria-controls="policy-viewer"
                @click="policyOpen = !policyOpen"
              >
                <FileText :size="15" aria-hidden="true" />
                {{ policyOpen ? 'Hide policy' : 'View policy' }}
              </button>
              <a
                v-if="policy.source_url"
                class="btn btn-quiet"
                :href="policy.source_url"
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink :size="15" aria-hidden="true" />
                {{ cmsLinkLabel }}
              </a>
            </div>
            <div id="policy-viewer">
              <PolicyViewer v-if="policyOpen" :policy-id="policyId(policy)" @close="policyOpen = false" />
            </div>
          </section>
        </div>

        <div v-else id="panel-decision" role="tabpanel" aria-labelledby="tab-decision" class="tab-panel">
          <section v-if="disposed" class="block" aria-labelledby="disposition-title">
            <h2 id="disposition-title" class="block-title">{{ dispositionTitle }}</h2>
            <template v-if="request.determination_status === 'approved'">
              <dl class="facts">
                <template v-if="authValidity">
                  <dt>Authorization valid</dt>
                  <dd class="num">{{ authValidity }}</dd>
                </template>
                <dt>Provider notified</dt>
                <dd class="num">
                  {{ request.notified_at ? formatDateTime(request.notified_at) : 'Approval letter drafted — not yet sent' }}
                </dd>
              </dl>
              <div v-if="!request.notified_at" class="block-actions">
                <button type="button" class="btn btn-primary" @click="store.navigate('letter-audit')">
                  <MailCheck :size="15" aria-hidden="true" />
                  Review and send letter
                </button>
              </div>
            </template>
            <template v-else-if="request.determination_status === 'pended'">
              <p class="block-lead">Items requested from the provider:</p>
              <ul class="gaps-list">
                <li v-for="(item, index) in request.requested_items" :key="index">{{ item }}</li>
              </ul>
              <dl class="facts">
                <dt>Provider notified</dt>
                <dd class="num">
                  {{ request.notified_at ? formatDateTime(request.notified_at) : 'Request letter drafted — not yet sent' }}
                </dd>
              </dl>
              <div v-if="!request.notified_at" class="block-actions">
                <button type="button" class="btn btn-primary" @click="store.navigate('letter-audit')">
                  <MailCheck :size="15" aria-hidden="true" />
                  Review and send letter
                </button>
              </div>
            </template>
            <template v-else>
              <p class="block-lead">Summary sent with the referral</p>
              <blockquote v-if="request.md_summary" class="summary-quote">{{ request.md_summary }}</blockquote>
              <p class="referral-note">
                <Info :size="14" aria-hidden="true" />
                Internal handoff — no provider letter is sent while the Medical Director reviews.
              </p>
            </template>
          </section>
          <div v-else class="absence">
            <h2>No disposition yet</h2>
            <p>Use the recommendation actions in the decision column to approve, request information, or refer to MD.</p>
          </div>

          <section
            v-if="disposed && determination && determination.gaps.length > 0"
            class="block"
            aria-labelledby="decision-gaps-title"
          >
            <h2 id="decision-gaps-title" class="block-title">Documentation gaps at decision time</h2>
            <ul class="gaps-list">
              <li v-for="(gap, index) in determination.gaps" :key="index">{{ gap }}</li>
            </ul>
          </section>

          <section v-if="attribution" class="block" aria-labelledby="attribution-title">
            <h2 id="attribution-title" class="block-title">How this recommendation was produced</h2>
            <dl class="facts">
              <dt>Engine</dt>
              <dd>{{ attribution.engine_label }}</dd>
              <dt>Model</dt>
              <dd class="num">{{ modelLabel }}</dd>
              <dt>Policy</dt>
              <dd>{{ policyLabel(request.policy) }}</dd>
              <dt>Evaluated at</dt>
              <dd class="num">{{ formatDateTime(attribution.evaluated_at) }}</dd>
            </dl>
            <div class="block-actions">
              <button type="button" class="btn" :disabled="disposing || state.evaluating" @click="rerun">
                <LoaderCircle v-if="state.evaluating" :size="15" class="spin" aria-hidden="true" />
                <RotateCw v-else :size="15" aria-hidden="true" />
                {{ state.evaluating ? 'Re-running analysis…' : 'Re-run analysis' }}
              </button>
            </div>
            <LlmInspector :request-id="request.id" :final-engine-label="attribution.engine_label" />
          </section>

          <section class="block" aria-labelledby="audit-title">
            <h2 id="audit-title" class="block-title">Audit trail</h2>
            <AuditTrail :events="request.audit_trail" />
          </section>
        </div>
      </div>
    </div>

    <section class="signature" :class="{ 'is-signed': signature }" aria-labelledby="signature-title">
      <h2 id="signature-title" class="signature-title">
        <Lock v-if="signature" :size="15" aria-hidden="true" />
        <PenLine v-else :size="15" aria-hidden="true" />
        <span>Sign-off</span>
        <span class="signature-state caption">{{ signature ? 'Signed and locked' : 'Not signed' }}</span>
      </h2>
      <dl class="boxes signature-boxes">
        <div class="box">
          <dt class="caption">Reviewer</dt>
          <dd class="box-value">{{ signature?.actor ?? '—' }}</dd>
        </div>
        <div class="box">
          <dt class="caption">Disposition</dt>
          <dd class="box-value">{{ signature ? dispositionTitle : 'Not signed' }}</dd>
        </div>
        <div class="box">
          <dt class="caption">Authorization valid</dt>
          <dd class="box-value num">{{ authValidity ?? '—' }}</dd>
        </div>
        <div class="box">
          <dt class="caption">Signed at</dt>
          <dd class="box-value num">{{ signature ? formatDateTime(signature.timestamp) : '—' }}</dd>
        </div>
        <div class="box">
          <dt class="caption">Provider letter</dt>
          <dd class="box-value num">{{ letterStatus }}</dd>
        </div>
      </dl>
    </section>
  </section>

  <section v-else class="page" aria-labelledby="no-case-title">
    <div class="absence">
      <h1 id="no-case-title" class="no-case-title">No case selected</h1>
      <p>Pick a request from the worklist to open its workspace.</p>
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
.workspace {
  display: grid;
  gap: var(--space-4);
}

.workspace .page-head {
  margin-bottom: 0;
}

.banner {
  margin: 0;
}

.banner dd {
  margin: 0;
}

.due-countdown {
  font-size: var(--text-small);
}

@media (min-width: 68rem) {
  .banner {
    grid-template-columns:
      minmax(0, 1fr) minmax(0, 0.8fr) minmax(0, 1.5fr) minmax(0, 1.7fr) minmax(0, 1.5fr)
      minmax(0, 0.7fr) minmax(0, 0.7fr) minmax(0, 1fr);
  }
}

.value-flag {
  color: var(--flag-deep);
  font-weight: 700;
}

.lifecycle {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 0;
  padding: 0;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
  list-style: none;
}

.stamp {
  display: grid;
  gap: 0.125rem;
  padding: 0.4375rem 0.75rem;
  border-left: 1px solid var(--rule);
  color: var(--ink-3);
}

.stamp:first-child {
  border-left: 0;
}

.stamp-value {
  font-size: var(--text-small);
  font-weight: 600;
}

.stamp.is-done {
  color: var(--ink);
}

.stamp.is-done .stamp-label {
  color: var(--ink-2);
}

.stamp.is-next {
  background: var(--action-wash);
  box-shadow: inset 0 -2px 0 var(--action);
}

.stamp.is-next .stamp-label {
  color: var(--action-deep);
}

.stamp.is-flag,
.stamp.is-flag .stamp-label {
  color: var(--flag-deep);
}

.workspace-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 21.5rem;
  grid-template-areas: 'main aside';
  gap: var(--space-5);
  align-items: start;
}

.decision {
  grid-area: aside;
  position: sticky;
  top: var(--space-4);
  display: grid;
  gap: var(--space-3);
  max-height: calc(100vh - 2rem);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.workspace-main {
  grid-area: main;
  display: grid;
  min-width: 0;
}

.decision-status {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  padding: var(--space-4);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
}

.decision-status > svg {
  flex: none;
  margin-top: 0.125rem;
  color: var(--action);
}

.decision-status > div {
  display: grid;
  gap: var(--space-2);
  justify-items: start;
}

.decision-status-flag {
  border-color: var(--flag);
  background: var(--flag-wash);
}

.decision-status-flag > svg {
  color: var(--flag);
}

.decision-status-title {
  font-weight: 700;
}

.decision-status-copy {
  color: var(--ink-2);
  font-size: var(--text-small);
}

.gaps {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
}

.gaps-title {
  font-size: var(--text-small);
  font-weight: 700;
}

.gaps-list {
  display: grid;
  gap: 0.375rem;
  margin: 0;
  padding-left: 1.125rem;
  font-size: var(--text-small);
}

.tab-panel {
  display: grid;
  gap: var(--space-5);
  padding-top: var(--space-4);
}

.block {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
}

.block + .block {
  padding-top: var(--space-5);
  border-top: 1px solid var(--rule);
}

.block-head {
  display: grid;
  gap: var(--space-1);
}

.block-title {
  font-size: var(--text-h3);
}

.block-lead {
  max-width: 72ch;
  color: var(--ink-2);
  font-size: var(--text-small);
}

.block-pair {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: var(--space-5);
  padding-top: var(--space-5);
  border-top: 1px solid var(--rule);
}

.block-pair + .block {
  padding-top: var(--space-5);
  border-top: 1px solid var(--rule);
}

.block-pair .block + .block {
  padding-top: 0;
  border-top: 0;
}

.block-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.record {
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  background: var(--paper);
  scroll-margin-top: var(--space-4);
}

.record:focus-visible {
  outline-offset: 2px;
}

.record-head {
  display: grid;
  gap: 0.125rem;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--rule);
  background: var(--surface);
}

.record-title {
  font-size: var(--text-body);
}

.record-text {
  max-width: 88ch;
  padding: var(--space-3) var(--space-4) var(--space-4);
  font-size: var(--text-small);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

#policy-basis {
  scroll-margin-top: var(--space-4);
}

.coverage-fact {
  display: flex;
  gap: 0.375rem;
  align-items: center;
}

.summary-quote {
  margin: 0;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  background: var(--paper);
  max-width: 72ch;
  white-space: pre-wrap;
}

.referral-note {
  display: flex;
  gap: 0.375rem;
  align-items: center;
  color: var(--ink-3);
  font-size: var(--text-small);
  font-weight: 600;
}

.signature {
  display: grid;
  grid-template-columns: 11rem minmax(0, 1fr);
  border-top: 1px solid var(--rule-strong);
  border-left: 1px solid var(--rule-strong);
}

.signature-title {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.125rem 0.5rem;
  align-content: center;
  align-items: center;
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-right: 1px solid var(--rule-strong);
  border-bottom: 1px solid var(--rule-strong);
  background: var(--sunk);
  font-size: var(--text-body);
}

.signature-title svg {
  color: var(--ink-3);
}

.signature-state {
  grid-column: 2;
}

.signature-boxes {
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 0;
  border-top: 0;
  border-left: 0;
}

.signature-boxes dd {
  margin: 0;
}

.signature:not(.is-signed) .box-value {
  color: var(--ink-3);
  font-weight: 400;
}

.signature.is-signed .signature-title svg {
  color: var(--action-deep);
}

.no-case-title {
  font-size: var(--text-h2);
}

@media (max-width: 68rem) {
  .workspace-layout {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      'main'
      'aside';
  }

  .decision {
    position: static;
    max-height: none;
    overflow: visible;
  }
}

@media (max-width: 48rem) {
  .signature {
    grid-template-columns: minmax(0, 1fr);
  }

  .signature-boxes {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .signature-boxes .box:last-child {
    grid-column: 1 / -1;
  }

  .lifecycle {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .stamp {
    border-top: 1px solid var(--rule);
  }

  .stamp:nth-child(-n + 2) {
    border-top: 0;
  }

  .stamp:nth-child(odd) {
    border-left: 0;
  }

  .stamp:last-child {
    grid-column: 1 / -1;
  }
}
</style>

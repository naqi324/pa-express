<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { CircleAlert, CircleCheck, TriangleAlert, X } from '@lucide/vue';
import CaseWorkspaceView from './components/CaseWorkspaceView.vue';
import ConnectionView from './components/ConnectionView.vue';
import LetterAuditView from './components/LetterAuditView.vue';
import NewRequestView from './components/NewRequestView.vue';
import QueueView from './components/QueueView.vue';
import { ENGINE_PRESENTATION } from './enginePresentation';
import { useScrollFade } from './scrollFade';
import type { ViewName } from './store';
import { useAppStore } from './store';
import { dismissToast, notify, useToasts } from './toast';

const store = useAppStore();

const { state } = store;

const toasts = useToasts();

const awaitingReview = computed(
  () => state.requests.filter((request) => request.determination_status === 'in_review').length,
);

const openCase = computed(() => state.currentRequest);

const letterAvailable = computed(() => {
  const status = openCase.value?.determination_status;

  return status === 'approved' || status === 'pended';
});

const engineName = computed(() => ENGINE_PRESENTATION[state.defaultEngine].name);

const tabStrip = ref<HTMLElement | null>(null);

useScrollFade(tabStrip, () => [state.view, openCase.value?.id ?? '', String(letterAvailable.value)].join(':'));

function isCurrent(view: ViewName): 'page' | undefined {
  return state.view === view ? 'page' : undefined;
}

watch(
  () => state.globalError,
  (message) => {
    if (!message) return;

    notify('error', message);
    store.clearGlobalError();
  },
);

onMounted(() => {
  void store.bootstrap();
});
</script>

<template>
  <header class="app-header">
    <div class="app-bar">
      <span class="wordmark">Prior Auth Express</span>
      <div class="app-status">
        <button
          v-if="state.health"
          type="button"
          class="engine-link"
          :title="`Reasoning engine for new requests: ${engineName}. Select to change.`"
          @click="store.navigate('connection')"
        >
          Engine: {{ engineName }}
        </button>
        <span v-else class="backend-down">
          <TriangleAlert :size="14" aria-hidden="true" />
          Backend offline
        </span>
        <span v-if="state.health" class="version num">v{{ state.health.version }}</span>
        <span class="demo-note">Demo — synthetic data, no PHI</span>
      </div>
    </div>
    <nav ref="tabStrip" class="app-tabs" aria-label="Primary">
      <button type="button" class="divider-tab" :aria-current="isCurrent('queue')" @click="store.navigate('queue')">
        Worklist
        <span v-if="awaitingReview > 0" class="tab-count">{{ awaitingReview }}</span>
      </button>
      <button
        type="button"
        class="divider-tab"
        :aria-current="isCurrent('new-request')"
        @click="store.navigate('new-request')"
      >
        New request
      </button>
      <button
        v-if="openCase"
        type="button"
        class="divider-tab"
        :aria-current="isCurrent('workspace')"
        @click="store.navigate('workspace')"
      >
        <span class="num">{{ openCase.id }}</span>
        <span class="tab-member">{{ openCase.member.name }}</span>
      </button>
      <button
        v-if="openCase && letterAvailable"
        type="button"
        class="divider-tab"
        :aria-current="isCurrent('letter-audit')"
        @click="store.navigate('letter-audit')"
      >
        Letter
      </button>
      <button
        type="button"
        class="divider-tab tab-end"
        :aria-current="isCurrent('connection')"
        @click="store.navigate('connection')"
      >
        Engine
      </button>
    </nav>
  </header>

  <main id="main">
    <QueueView v-if="state.view === 'queue'" />
    <NewRequestView v-else-if="state.view === 'new-request'" />
    <CaseWorkspaceView v-else-if="state.view === 'workspace'" />
    <LetterAuditView v-else-if="state.view === 'letter-audit'" />
    <ConnectionView v-else-if="state.view === 'connection'" />
  </main>

  <div class="toasts" aria-live="polite" aria-relevant="additions">
    <div v-for="toast in toasts" :key="toast.id" class="toast" :class="`toast-${toast.kind}`">
      <CircleCheck v-if="toast.kind === 'success'" :size="18" aria-hidden="true" />
      <CircleAlert v-else :size="18" aria-hidden="true" />
      <p>{{ toast.message }}</p>
      <button type="button" class="toast-close" aria-label="Dismiss notification" @click="dismissToast(toast.id)">
        <X :size="16" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.app-header {
  background: var(--binder);
  color: var(--surface);
}

.app-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2) var(--space-5);
  padding: 0.625rem var(--page-inline) 0.5rem;
}

.wordmark {
  font-size: var(--text-lead);
  font-weight: 800;
  letter-spacing: -0.01em;
}

.app-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-4);
  font-size: var(--text-small);
  color: var(--binder-text);
}

.engine-link {
  padding: 0.125rem 0.5rem;
  border: 1px solid var(--binder-rule);
  border-radius: var(--radius);
  background: transparent;
  color: var(--surface);
  font-size: var(--text-small);
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color var(--tint),
    border-color var(--tint);
}

.engine-link:hover {
  background: var(--binder-tab);
  border-color: var(--binder-text);
}

.engine-link:focus-visible,
.app-tabs .divider-tab:focus-visible,
.toast-close:focus-visible {
  outline-color: var(--binder-focus);
}

.backend-down {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.125rem 0.5rem;
  border-radius: var(--radius);
  background: var(--flag);
  color: var(--paper);
  font-weight: 700;
}

.app-tabs {
  display: flex;
  align-items: flex-end;
  gap: 0.25rem;
  position: relative;
  padding: 0.25rem var(--page-inline) 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.app-tabs .divider-tab {
  margin-bottom: 0;
  border-color: var(--binder-tab);
  background: var(--binder-tab);
  color: var(--binder-text);
}

.app-tabs .divider-tab:hover {
  background: var(--binder-hover);
  color: var(--surface);
}

.app-tabs .divider-tab[aria-current='page'] {
  border-color: var(--surface);
  background: var(--surface);
  color: var(--ink);
}

.app-tabs .divider-tab[aria-current='page']::before {
  content: '';
  position: absolute;
  inset: -1px -1px auto;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: var(--action);
}

.app-tabs .tab-count {
  min-width: 1.25rem;
  padding: 0 0.3125rem;
  border-radius: 2px;
  background: var(--action);
  color: var(--paper);
  font-size: var(--text-caption);
  text-align: center;
}

.tab-member {
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 400;
}

.tab-end {
  margin-left: auto;
}

.version,
.demo-note {
  white-space: nowrap;
}

.toasts {
  position: fixed;
  right: var(--space-4);
  bottom: var(--space-4);
  z-index: 50;
  display: grid;
  gap: var(--space-2);
  width: min(26rem, calc(100vw - 2rem));
}

.toast {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 0.625rem;
  align-items: start;
  padding: 0.75rem 0.5rem 0.75rem 0.875rem;
  border: 1px solid var(--binder);
  border-radius: var(--radius);
  background: var(--binder);
  color: var(--surface);
  box-shadow: var(--shadow-lift);
  animation: toast-in 200ms var(--ease-out);
}

.toast > svg {
  margin-top: 0.125rem;
  color: var(--binder-focus);
}

.toast-error {
  border-color: var(--flag);
  background: var(--flag-wash);
  color: var(--ink);
}

.toast-error > svg {
  color: var(--flag);
}

.toast-close {
  display: inline-grid;
  place-items: center;
  width: 1.75rem;
  height: 1.75rem;
  border: 0;
  border-radius: var(--radius);
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.toast-close:hover {
  background: rgb(127 140 153 / 22%);
}

.toast-error .toast-close:focus-visible {
  outline-color: var(--action);
}

@keyframes toast-in {
  from {
    transform: translateY(6px);
  }
}
</style>

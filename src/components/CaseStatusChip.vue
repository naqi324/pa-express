<script setup lang="ts">
import { computed } from 'vue';
import type { Component } from 'vue';
import { CircleCheck, CirclePause, ClipboardCheck, LoaderCircle, Mail, Stethoscope, TriangleAlert } from '@lucide/vue';
import type { DeterminationStatus, ProcessingStatus } from '../types';

// One reviewer-facing status per case, collapsing the pipeline state and the
// human disposition into the value a reviewer thinks in. Pipeline states the
// reviewer cannot act on (Received, Analyzing) render as plain text.
const props = defineProps<{
  processing: ProcessingStatus;
  determination: DeterminationStatus;
  notified?: boolean;
}>();

interface StatusFace {
  label: string;
  tone: string;
  icon: Component | null;
  spinning: boolean;
}

function face(label: string, tone: string, icon: Component | null, spinning = false): StatusFace {
  return { label, tone, icon, spinning };
}

const current = computed<StatusFace>(() => {
  if (props.determination === 'approved') return face('Approved', '', props.notified ? Mail : CircleCheck);

  if (props.determination === 'pended') return face('Pended', '', props.notified ? Mail : CirclePause);

  if (props.determination === 'referred_md') return face('Referred to MD', '', Stethoscope);

  if (props.processing === 'queued') return face('Received', 'code-text', null);

  if (props.processing === 'analyzing') return face('Analyzing…', 'code-text', LoaderCircle, true);

  if (props.processing === 'failed') return face('Analysis failed', 'code-flag-soft', TriangleAlert);

  return face('Needs review', 'code-action', ClipboardCheck);
});

const detail = computed(() => {
  const base = `Pipeline: ${props.processing.replaceAll('_', ' ')} · Disposition: ${props.determination.replaceAll('_', ' ')}`;

  return props.notified ? `${base} · Letter sent` : base;
});
</script>

<template>
  <span class="code" :class="current.tone" :title="detail">
    <component
      :is="current.icon"
      v-if="current.icon"
      :size="13"
      :stroke-width="2.25"
      :class="{ spin: current.spinning }"
      aria-hidden="true"
    />
    {{ current.label }}
    <span v-if="notified" class="visually-hidden">, letter sent</span>
  </span>
</template>

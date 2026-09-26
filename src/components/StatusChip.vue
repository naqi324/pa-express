<script setup lang="ts">
import { computed } from 'vue';
import { Check, CircleQuestionMark, X } from '@lucide/vue';
import { verdictLabel } from '../format';
import type { CriterionStatus } from '../types';

// Criterion verdict code. Not met is the strongest mark because it is the
// reason a reviewer pends; Met stays in ink.
const props = defineProps<{
  value: CriterionStatus;
}>();

const CLASSES: Record<CriterionStatus, string> = {
  MET: '',
  NOT_MET: 'code-flag',
  INSUFFICIENT: 'code-flag-soft',
};

const label = computed(() => verdictLabel(props.value));
</script>

<template>
  <span class="code" :class="CLASSES[value]">
    <Check v-if="value === 'MET'" :size="13" :stroke-width="2.5" aria-hidden="true" />
    <X v-else-if="value === 'NOT_MET'" :size="13" :stroke-width="2.5" aria-hidden="true" />
    <CircleQuestionMark v-else :size="13" :stroke-width="2.25" aria-hidden="true" />
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { CircleCheck, FileQuestionMark } from '@lucide/vue';
import type { ProcessingStatus, Recommendation } from '../types';

// The recommendation is advice, not a state: icon and text, never a tag.
const props = defineProps<{
  recommendation: Recommendation | null;
  processing?: ProcessingStatus;
}>();

const label = computed(() => {
  if (props.recommendation === 'approve') return 'Meets criteria';

  if (props.recommendation === 'pend') return 'Needs info';

  if (props.processing === 'queued' || props.processing === 'analyzing') return 'Awaiting analysis';

  return '—';
});
</script>

<template>
  <span class="recommendation" :class="{ 'recommendation-pend': recommendation === 'pend', 'recommendation-none': !recommendation }">
    <CircleCheck v-if="recommendation === 'approve'" :size="15" aria-hidden="true" />
    <FileQuestionMark v-else-if="recommendation === 'pend'" :size="15" aria-hidden="true" />
    <span v-if="recommendation" class="visually-hidden">Recommendation:</span>
    {{ label }}
  </span>
</template>

<style scoped>
.recommendation {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  font-weight: 600;
  white-space: nowrap;
}

.recommendation svg {
  flex: none;
}

.recommendation-pend {
  color: var(--flag-deep);
}

.recommendation-none {
  color: var(--ink-3);
  font-weight: 400;
}
</style>

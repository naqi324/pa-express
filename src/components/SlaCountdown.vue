<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ChevronsUp, Clock, TriangleAlert } from '@lucide/vue';

// Time-to-decision readout. Overdue always wins the icon; expedited cases
// show the expedited mark; under four hours the time turns to the flag color.
const props = defineProps<{
  dueAt: string;
  expedited?: boolean;
}>();

const URGENT_MS = 4 * 60 * 60 * 1000;

const now = ref(Date.now());

let timer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  timer = setInterval(() => {
    now.value = Date.now();
  }, 30_000);
});

onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});

const remainingMs = computed(() => new Date(props.dueAt).getTime() - now.value);

const overdue = computed(() => remainingMs.value < 0);

const urgent = computed(() => !overdue.value && remainingMs.value < URGENT_MS);

const label = computed(() => {
  const totalMinutes = Math.floor(Math.abs(remainingMs.value) / 60_000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;

  let span = `${minutes}m`;

  if (days > 0) span = `${days}d ${hours}h`;
  else if (hours > 0) span = `${hours}h ${minutes}m`;

  return overdue.value ? `Overdue ${span}` : `${span} left`;
});

const title = computed(() => {
  if (overdue.value) return 'Decision overdue';

  if (props.expedited) return 'Expedited — 72-hour decision window';

  return 'Time until decision due';
});
</script>

<template>
  <span class="sla num" :class="{ 'sla-flag': overdue || urgent, 'sla-overdue': overdue }" :title="title">
    <TriangleAlert v-if="overdue" :size="14" :stroke-width="2.25" aria-hidden="true" />
    <ChevronsUp v-else-if="expedited" :size="14" :stroke-width="2.5" aria-hidden="true" />
    <Clock v-else :size="14" aria-hidden="true" />
    <span>{{ label }}</span>
    <span v-if="expedited && !overdue" class="visually-hidden">(expedited)</span>
  </span>
</template>

<style scoped>
.sla {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  font-weight: 600;
  white-space: nowrap;
}

.sla svg {
  flex: none;
  color: var(--ink-2);
}

.sla-flag,
.sla-flag svg {
  color: var(--flag-deep);
}

.sla-overdue {
  font-weight: 800;
}
</style>

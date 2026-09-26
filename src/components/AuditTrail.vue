<script setup lang="ts">
import { ArrowRight } from '@lucide/vue';
import type { AuditEvent } from '../types';

defineProps<{
  events: AuditEvent[];
}>();

const EVENT_LABELS = new Map([
  ['request_created', 'Request received'],
  ['evaluation_started', 'Analysis started'],
  ['evaluation_completed', 'Analysis completed'],
  ['evaluation_failed', 'Analysis failed'],
  ['human_action_approve', 'Approved by reviewer'],
  ['human_action_pend', 'Information requested'],
  ['human_action_refer_md', 'Referred to Medical Director'],
  ['letter_edited', 'Letter draft edited'],
  ['letter_sent', 'Letter sent to provider'],
]);

// human_action_* events can carry a ": note" suffix; label the prefix and keep the note.
function eventLabel(event: string): string {
  const direct = EVENT_LABELS.get(event);

  if (direct) return direct;

  const separator = event.indexOf(': ');

  if (separator > 0) {
    const prefix = EVENT_LABELS.get(event.slice(0, separator));

    if (prefix) return `${prefix} — ${event.slice(separator + 2)}`;
  }

  return event.replaceAll('_', ' ').replace(/^./, (first) => first.toUpperCase());
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);

  if (Number.isNaN(date.getTime())) return iso;

  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  });
}

function stateLabel(state: string): string {
  return state.replaceAll('_', ' ');
}
</script>

<template>
  <div class="audit-scroll">
    <table class="ruled audit">
      <thead>
        <tr>
          <th scope="col" class="audit-time">Time</th>
          <th scope="col">Event</th>
          <th scope="col">Transition</th>
          <th scope="col">Actor</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(entry, index) in events" :key="`${entry.timestamp}-${index}`">
          <td class="audit-time num">
            <time :datetime="entry.timestamp">{{ formatTimestamp(entry.timestamp) }}</time>
          </td>
          <td class="audit-event">
            {{ eventLabel(entry.event) }}
            <time class="audit-when num" :datetime="entry.timestamp">{{ formatTimestamp(entry.timestamp) }}</time>
          </td>
          <td class="audit-transition">
            <span v-if="entry.from_state || entry.to_state" class="transition">
              <span v-if="entry.from_state">{{ stateLabel(entry.from_state) }}</span>
              <ArrowRight v-if="entry.from_state && entry.to_state" :size="13" aria-label="to" />
              <span v-if="entry.to_state">{{ stateLabel(entry.to_state) }}</span>
            </span>
            <span v-else class="muted">—</span>
          </td>
          <td class="audit-actor">{{ entry.actor }}</td>
        </tr>
        <tr v-if="events.length === 0">
          <td colspan="4" class="muted">No events recorded yet.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.audit-scroll {
  position: relative;
  overflow-x: auto;
  container-type: inline-size;
}

.audit {
  font-size: var(--text-small);
}

.audit-time {
  white-space: nowrap;
  color: var(--ink-2);
}

.audit-event {
  min-width: 12rem;
  font-weight: 600;
}

.transition {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  white-space: nowrap;
  color: var(--ink-2);
}

.audit-actor {
  min-width: 9rem;
}

.audit-when {
  display: none;
}

/* Narrow columns (the letter view) move the time under the event. */
@container (max-width: 40rem) {
  .audit-time {
    display: none;
  }

  .audit-when {
    display: block;
    color: var(--ink-2);
    font-size: var(--text-caption);
    font-weight: 400;
  }

  .audit-event,
  .audit-actor {
    min-width: 0;
  }

  .transition {
    flex-wrap: wrap;
    white-space: normal;
  }
}
</style>

<script setup lang="ts">
import { computed } from 'vue';
import { FileText, Flag } from '@lucide/vue';
import type { EvidenceCitation } from '../types';

// A flagged quote backs a criterion that is not met. A run of underscores in
// the quote means the form field was left empty in the source record.
const props = defineProps<{
  citation: EvidenceCitation;
  active?: boolean;
  flagged?: boolean;
}>();

const BLANK_FIELD = /_{3,}/;

const emit = defineEmits<{
  open: [];
}>();

const blankField = computed(() => BLANK_FIELD.test(props.citation.quote));

const sourceLine = computed(() => {
  const { source_document: source, document_date: date } = props.citation;

  return date ? `${source} — ${date}` : source;
});
</script>

<template>
  <figure class="evidence" :class="{ 'evidence-active': active, 'evidence-flagged': flagged }">
    <blockquote class="evidence-quote">“{{ citation.quote }}”</blockquote>
    <figcaption class="evidence-caption">
      <span v-if="flagged && blankField" class="evidence-gap">
        <Flag :size="12" :stroke-width="2.5" aria-hidden="true" />
        Field blank in record
      </span>
      <button
        type="button"
        class="evidence-source"
        :title="`Open ${citation.source_document} with this passage highlighted`"
        @click="emit('open')"
      >
        <FileText :size="13" aria-hidden="true" />
        <span class="num">{{ sourceLine }}</span>
      </button>
    </figcaption>
  </figure>
</template>

<style scoped>
.evidence {
  display: grid;
  gap: 0.375rem;
  margin: 0;
  padding: 0.5rem 0.75rem 0.5rem 0.875rem;
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  background: var(--paper);
  transition:
    border-color var(--tint),
    background-color var(--tint);
}

.evidence-active {
  border-color: var(--action);
  background: var(--action-wash);
}

.evidence-flagged {
  border-color: var(--flag);
}

.evidence-flagged.evidence-active {
  background: var(--flag-wash);
}

.evidence-quote {
  margin: 0;
  text-indent: -0.4em;
  line-height: 1.5;
}

.evidence-caption {
  display: grid;
  gap: 0.25rem;
  justify-items: start;
}

.evidence-gap {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  color: var(--flag-deep);
  font-size: var(--text-small);
  font-weight: 700;
}

.evidence-source {
  display: inline-flex;
  align-items: flex-start;
  gap: 0.3125rem;
  padding: 0;
  border: 0;
  background: none;
  color: var(--action-deep);
  font-size: var(--text-small);
  font-weight: 600;
  text-align: left;
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 0.2em;
  cursor: pointer;
}

.evidence-source svg {
  flex: none;
  margin-top: 0.1875rem;
}

.evidence-source:hover {
  color: var(--ink);
}
</style>

<script setup lang="ts">
import { computed } from 'vue'
import type { Block } from '../chat/turn'

const props = defineProps<{ step: Extract<Block, { kind: 'query' }> }>()

const PREVIEW_ROWS = 8

// TODO(ui-harden): Pluralize row counts and handle a missing total
// WHY: the summary reads "1 rows", or "undefined rows" when total_rows is absent
// DONE-WHEN: summaries read "1 row", "2,304 rows", and "Queried the data" when totalRows is undefined

// TODO(ui-clarify): Say "corrected it" only when a later query in the turn succeeded
// WHY: the failed-step label claims a correction that may never have happened
// DONE-WHEN: a turn whose only query failed shows "Query failed" without "corrected it"

// TODO(ui-a11y): Show the "show SQL" cue on keyboard focus and to touch users
// WHY: the cue only appears on hover, so keyboard and touch users see an unlabeled muted line
// DONE-WHEN: tabbing to a query step shows "show SQL" next to its summary
const summary = computed(() => {
  switch (props.step.status) {
    case 'running':
      return 'Querying the data'
    case 'failed':
      return 'Query failed, the assistant corrected it'
    case 'done':
      return `Queried the data, ${props.step.totalRows?.toLocaleString('en-US')} rows`
  }
})
const rows = computed(() => props.step.rows?.slice(0, PREVIEW_ROWS) ?? [])
</script>

<template>
  <details class="step" :class="step.status">
    <summary>
      <span class="dot" aria-hidden="true" />
      {{ summary }}
    </summary>
    <p v-if="step.error" class="error">{{ step.error }}</p>
    <pre><code>{{ step.sql.trim() }}</code></pre>
    <div v-if="rows.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th v-for="column in step.columns" :key="column.name">{{ column.name }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="index">
            <td v-for="column in step.columns" :key="column.name">{{ row[column.name] }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="(step.totalRows ?? 0) > rows.length" class="more">
        First {{ rows.length }} of {{ step.totalRows?.toLocaleString('en-US') }} rows
      </p>
    </div>
  </details>
</template>

<style scoped>
.step {
  font-family: var(--font-ui);
  font-size: 0.8rem;
  color: var(--ink-muted);
  margin: 0.35rem 0;
}

summary {
  cursor: pointer;
  list-style: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.2rem 0;
}

summary::-webkit-details-marker {
  display: none;
}

summary::after {
  content: 'show SQL';
  font-size: 0.72rem;
  color: var(--accent);
  opacity: 0;
  transition: opacity 0.15s;
}

summary:hover::after {
  opacity: 1;
}

.step[open] summary::after {
  content: 'hide SQL';
  opacity: 1;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--good);
}

.running .dot {
  background: var(--accent);
  animation: pulse 1s ease-in-out infinite;
}

.failed .dot {
  background: var(--warning);
}

@keyframes pulse {
  50% {
    opacity: 0.25;
  }
}

.error {
  color: var(--warning-ink);
  margin: 0.4rem 0;
}

pre {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  line-height: 1.5;
  background: var(--surface-sunken);
  border: 1px solid var(--rule);
  border-radius: 6px;
  padding: 0.75rem;
  max-height: 16rem;
  overflow: auto;
  color: var(--ink-secondary);
}

.table-wrap {
  overflow-x: auto;
  margin-top: 0.5rem;
}

table {
  border-collapse: collapse;
  font-variant-numeric: tabular-nums;
}

th,
td {
  text-align: left;
  padding: 0.25rem 0.9rem 0.25rem 0;
  border-bottom: 1px solid var(--rule);
  white-space: nowrap;
}

th {
  font-weight: 600;
  color: var(--ink-secondary);
}

.more {
  margin-top: 0.3rem;
}
</style>

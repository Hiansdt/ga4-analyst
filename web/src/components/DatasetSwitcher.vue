<script setup lang="ts">
import type { DatasetInfo } from '../api/types'

defineProps<{ datasets: DatasetInfo[]; selected: string; disabled: boolean }>()
const emit = defineEmits<{ select: [dataset: string] }>()
</script>

<template>
  <!-- Native radios: arrow keys move between datasets, and a disabled fieldset disables them all. -->
  <fieldset class="switcher" :disabled="disabled">
    <legend class="visually-hidden">Dataset</legend>
    <label v-for="dataset in datasets" :key="dataset.id" :class="{ active: dataset.id === selected }">
      <input
        type="radio"
        name="dataset"
        :value="dataset.id"
        :checked="dataset.id === selected"
        @change="emit('select', dataset.id)"
      />
      {{ dataset.name }}
    </label>
  </fieldset>
</template>

<style scoped>
.switcher {
  display: inline-flex;
  gap: 2px;
  margin: 0;
  padding: 2px;
  border: 1px solid var(--rule-strong);
  border-radius: 8px;
  background: var(--surface-sunken);
  font-family: var(--font-ui);
  font-size: 0.8rem;
}

label {
  position: relative;
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  color: var(--ink-secondary);
  cursor: pointer;
  white-space: nowrap;
}

label.active {
  color: var(--ink);
  font-weight: 600;
  background: var(--surface-raised);
  box-shadow: 0 1px 2px rgb(11 11 11 / 0.08);
}

label:has(input:focus-visible) {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.switcher:disabled label {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>

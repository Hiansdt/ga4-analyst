<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { loadDatasets } from './api/client'
import type { DatasetInfo } from './api/types'
import { pickDataset } from './chat/datasets'
import ChatView from './components/ChatView.vue'
import DatasetSwitcher from './components/DatasetSwitcher.vue'

const datasets = ref<DatasetInfo[]>([])
const selectedId = ref<string | null>(null)
const busy = ref(false)
const failed = ref(false)
const selected = computed(() => datasets.value.find((dataset) => dataset.id === selectedId.value) ?? null)

onMounted(async () => {
  try {
    datasets.value = await loadDatasets()
    selectedId.value = pickDataset(location.search, datasets.value)
  } catch {
    failed.value = true
  }
})

// The URL names the dataset, so a link opens the same one.
watch(selected, (dataset) => {
  if (!dataset) return
  const url = new URL(location.href)
  url.searchParams.set('dataset', dataset.id)
  history.replaceState(null, '', url)
  document.title = `${dataset.name} · Analyst`
})
</script>

<template>
  <header class="masthead">
    <div class="brand">
      <span class="mark" aria-hidden="true" />
      Analyst
    </div>
    <DatasetSwitcher
      v-if="datasets.length > 1 && selectedId"
      :datasets="datasets"
      :selected="selectedId"
      :disabled="busy"
      @select="selectedId = $event"
    />
    <div id="masthead-actions" class="actions" />
  </header>

  <p v-if="failed" class="unavailable" role="alert">
    The analyst is unavailable right now. Please try again in a minute.
  </p>
  <ChatView v-if="selected" :key="selected.id" :dataset="selected" @busy="busy = $event" />
</template>

<style scoped>
.masthead {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem 1rem;
  padding: 0.75rem 1.25rem;
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--rule);
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-family: var(--font-ui);
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.mark {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background: linear-gradient(135deg, var(--accent) 50%, var(--accent-2) 50%);
}

.actions {
  margin-left: auto;
}

.unavailable {
  width: min(46rem, 100% - 2rem);
  margin: 2rem auto;
  font-family: var(--font-ui);
  font-size: 0.9rem;
  color: var(--warning-ink);
  background: var(--warning-wash);
  border-radius: 6px;
  padding: 0.7rem 0.9rem;
}
</style>

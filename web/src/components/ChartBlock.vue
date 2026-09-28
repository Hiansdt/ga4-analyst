<script setup lang="ts">
import { onBeforeUnmount, onMounted, useTemplateRef } from 'vue'
import type { ChartSpec } from '../api/types'
import { echarts } from '../charts/echarts'
import { buildOption } from '../charts/options'

// TODO(ui-a11y): Expose each chart's data to screen readers as a table
// WHY: charts are role="img" labeled only by their title; the values live in hover tooltips
// DONE-WHEN: every rendered chart has aria-describedby pointing to a visually hidden table with the same rows, and axe reports no violations on it
const props = defineProps<{ chart: ChartSpec }>()
const container = useTemplateRef<HTMLDivElement>('container')

let instance: ReturnType<typeof echarts.init> | undefined
let observer: ResizeObserver | undefined

onMounted(() => {
  if (!container.value) return
  instance = echarts.init(container.value, undefined, { renderer: 'svg' })
  instance.setOption(buildOption(props.chart))
  observer = new ResizeObserver(() => instance?.resize())
  observer.observe(container.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  instance?.dispose()
})
</script>

<template>
  <figure class="chart">
    <figcaption>{{ chart.title }}</figcaption>
    <div ref="container" class="chart-canvas" role="img" :aria-label="chart.title" />
  </figure>
</template>

<style scoped>
.chart {
  margin: 1.25rem 0;
  padding: 1rem 1rem 0.5rem;
  background: var(--surface-raised);
  border: 1px solid var(--rule);
  border-radius: 6px;
}

figcaption {
  font-family: var(--font-ui);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--ink-secondary);
  margin-bottom: 0.5rem;
}

.chart-canvas {
  height: 300px;
}
</style>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, useTemplateRef } from 'vue'
import type { ChartSpec } from '../api/types'
import { echarts } from '../charts/echarts'
import { buildOption } from '../charts/options'

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

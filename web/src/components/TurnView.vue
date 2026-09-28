<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
import type { Turn } from '../chat/turn'
import MarkdownText from './MarkdownText.vue'
import QueryStep from './QueryStep.vue'

const props = defineProps<{ turn: Turn }>()

// TODO(ui-harden): Treat text followed only by charts as answer text, not narration
// WHY: when the model writes its answer before calling create_chart, the answer is styled as muted narration
// DONE-WHEN: a component test rendering a turn with blocks [text, chart] finds no .narration element

// TODO(ui-harden): Add a "Try again" button on a failed turn that re-sends its question
// WHY: after a failure the user has to retype the question from memory
// DONE-WHEN: a turn_failed event renders a "Try again" button whose click calls ask() with the same question text
// Text written right before a tool call is the model narrating its steps, not part of the answer.
function isNarration(index: number): boolean {
  const next = props.turn.blocks[index + 1]
  return next !== undefined && next.kind !== 'text'
}

// ECharts is most of the bundle; load it with the first chart instead of on page load.
const ChartBlock = defineAsyncComponent(() => import('./ChartBlock.vue'))
</script>

<template>
  <article class="turn">
    <h2 class="question">{{ turn.question }}</h2>
    <div class="answer">
      <template v-for="(block, index) in turn.blocks" :key="index">
        <MarkdownText
          v-if="block.kind === 'text'"
          :text="block.text"
          :class="{ narration: isNarration(index) }"
        />
        <QueryStep v-else-if="block.kind === 'query'" :step="block" />
        <ChartBlock v-else-if="block.kind === 'chart'" :chart="block.chart" />
        <p v-else class="working">Drawing a chart</p>
      </template>
      <p v-if="turn.status === 'streaming' && !turn.blocks.length" class="working">Thinking about the question</p>
      <p v-if="turn.status === 'failed'" class="failed" role="alert">
        {{ turn.error }} You can ask again.
      </p>
    </div>
  </article>
</template>

<style scoped>
.turn {
  padding: 2rem 0;
  border-bottom: 1px solid var(--rule);
  animation: rise 0.35s ease-out;
}

.question {
  font-family: var(--font-ui);
  font-size: 1rem;
  font-weight: 600;
  color: var(--ink);
  padding-left: 0.9rem;
  border-left: 3px solid var(--accent);
  margin-bottom: 1rem;
}

.answer .narration {
  font-size: 0.9rem;
  color: var(--ink-muted);
}

.working {
  font-family: var(--font-ui);
  font-size: 0.8rem;
  color: var(--ink-muted);
  animation: breathe 1.4s ease-in-out infinite;
}

.failed {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  color: var(--warning-ink);
  background: var(--warning-wash);
  border-radius: 6px;
  padding: 0.6rem 0.8rem;
  margin-top: 0.75rem;
}

@keyframes breathe {
  50% {
    opacity: 0.4;
  }
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}
</style>

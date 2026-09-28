<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
import { isNarration, type Turn } from '../chat/turn'
import MarkdownText from './MarkdownText.vue'
import QueryStep from './QueryStep.vue'

defineProps<{ turn: Turn; showFollowUps: boolean }>()
const emit = defineEmits<{ ask: [question: string] }>()

// TODO(ui-harden): Add a "Try again" button on a failed turn that re-sends its question
// WHY: after a failure the user has to retype the question from memory
// DONE-WHEN: a turn_failed event renders a "Try again" button whose click calls ask() with the same question text

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
          :class="{ narration: isNarration(turn.blocks, index) }"
        />
        <QueryStep v-else-if="block.kind === 'query'" :step="block" />
        <ChartBlock v-else-if="block.kind === 'chart'" :chart="block.chart" />
        <p v-else class="working">Drawing a chart</p>
      </template>
      <p v-if="turn.status === 'streaming' && !turn.blocks.length" class="working">Thinking about the question</p>
      <p v-if="turn.status === 'failed'" class="failed" role="alert">
        {{ turn.error }} You can ask again.
      </p>
      <div
        v-if="showFollowUps && turn.status === 'done' && turn.followUps?.length"
        class="follow-ups"
        role="group"
        aria-label="Suggested next questions"
      >
        <button v-for="question in turn.followUps" :key="question" type="button" @click="emit('ask', question)">
          {{ question }}
        </button>
      </div>
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

.follow-ups {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1.1rem;
}

.follow-ups button {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  text-align: left;
  color: var(--ink-secondary);
  background: var(--surface-raised);
  border: 1px solid var(--rule-strong);
  border-radius: 7px;
  padding: 0.45rem 0.75rem;
  cursor: pointer;
  transition:
    color 0.15s,
    border-color 0.15s;
}

.follow-ups button:hover {
  color: var(--ink);
  border-color: var(--accent);
}

.follow-ups button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
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

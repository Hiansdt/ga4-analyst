<script setup lang="ts">
import { nextTick, onMounted, useTemplateRef, watch } from 'vue'
import type { DatasetInfo } from '../api/types'
import { useChat } from '../chat/useChat'
import ChatComposer from './ChatComposer.vue'
import EmptyState from './EmptyState.vue'
import TurnView from './TurnView.vue'

// One dataset's chat. The parent remounts it (keyed by dataset) on a switch, so a streaming
// answer can never land in another dataset's conversation.
const props = defineProps<{ dataset: DatasetInfo }>()
const emit = defineEmits<{ busy: [busy: boolean] }>()

const { turns, busy, notice, restore, ask, newChat } = useChat(props.dataset.id)
const end = useTemplateRef<HTMLDivElement>('end')

onMounted(restore)
watch(busy, (value) => emit('busy', value))

// TODO(ui-harden): Auto-scroll only when the reader is already near the bottom
// WHY: scrolling up to read SQL mid-answer gets pulled back down on every text delta
// DONE-WHEN: scrolled 400px above the bottom while an answer streams, the view stays put; at the bottom it keeps following

// TODO(ui-a11y): Replace the page-wide live region with short status announcements
// WHY: the whole transcript is aria-live and the answer re-renders on every text delta, so screen readers repeat fragments
// DONE-WHEN: with Orca or NVDA, asking a question announces "Running query" and "Answer ready" once each instead of the streaming text

// Follow the answer as it streams in.
watch(
  () => turns.value.at(-1),
  () => nextTick(() => end.value?.scrollIntoView({ block: 'end' })),
  { deep: true },
)
</script>

<template>
  <!-- The masthead owns the slot; the button belongs to this chat. -->
  <Teleport defer to="#masthead-actions">
    <button v-if="turns.length" type="button" class="new-chat" :disabled="busy" @click="newChat">New chat</button>
  </Teleport>

  <main class="page">
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <EmptyState v-if="!turns.length" :dataset="dataset" @ask="ask" />
    <section v-else class="log" role="log" aria-live="polite">
      <TurnView
        v-for="(turn, index) in turns"
        :key="index"
        :turn="turn"
        :show-follow-ups="index === turns.length - 1 && !busy"
        @ask="ask"
      />
    </section>
    <div ref="end" />
  </main>

  <footer class="dock">
    <div class="page">
      <ChatComposer :busy="busy" @ask="ask" />
    </div>
  </footer>
</template>

<style scoped>
.new-chat {
  font-family: var(--font-ui);
  font-size: 0.8rem;
  color: var(--ink-secondary);
  background: transparent;
  border: 1px solid var(--rule-strong);
  border-radius: 7px;
  padding: 0.35rem 0.75rem;
  cursor: pointer;
}

.new-chat:hover:not(:disabled) {
  color: var(--ink);
  border-color: var(--ink-secondary);
}

.page {
  width: min(46rem, 100% - 2rem);
  margin-inline: auto;
}

main.page {
  padding-bottom: 9rem;
}

.notice {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  color: var(--ink-secondary);
  background: var(--surface-sunken);
  border-radius: 6px;
  padding: 0.6rem 0.8rem;
  margin-top: 1.25rem;
}

.dock {
  position: fixed;
  inset: auto 0 0;
  padding: 1rem 0 1.25rem;
  background: linear-gradient(to top, var(--surface) 70%, transparent);
}
</style>

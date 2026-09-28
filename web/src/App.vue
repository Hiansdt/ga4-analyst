<script setup lang="ts">
import { nextTick, onMounted, useTemplateRef, watch } from 'vue'
import { useChat } from './chat/useChat'
import ChatComposer from './components/ChatComposer.vue'
import EmptyState from './components/EmptyState.vue'
import TurnView from './components/TurnView.vue'

const { turns, busy, notice, restore, ask, newChat } = useChat()
const end = useTemplateRef<HTMLDivElement>('end')

onMounted(restore)

// Follow the answer as it streams in.
watch(
  () => turns.value.at(-1),
  () => nextTick(() => end.value?.scrollIntoView({ block: 'end' })),
  { deep: true },
)
</script>

<template>
  <header class="masthead">
    <div class="brand">
      <span class="mark" aria-hidden="true" />
      GA4 Analyst
    </div>
    <button v-if="turns.length" type="button" class="new-chat" :disabled="busy" @click="newChat">New chat</button>
  </header>

  <main class="page">
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <EmptyState v-if="!turns.length" @ask="ask" />
    <section v-else class="log" role="log" aria-live="polite">
      <TurnView v-for="(turn, index) in turns" :key="index" :turn="turn" />
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
.masthead {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1.25rem;
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

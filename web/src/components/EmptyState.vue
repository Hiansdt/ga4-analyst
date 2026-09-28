<script setup lang="ts">
defineEmits<{ ask: [question: string] }>()

const SUGGESTIONS = [
  'How are we doing?',
  'Where do customers drop off before buying?',
  'Which acquisition channel brings in the most revenue?',
  'Show me daily revenue in December 2020.',
]
</script>

<template>
  <section class="empty">
    <p class="kicker">Google Merchandise Store, Nov 2020 to Jan 2021</p>
    <h1>Ask the store's data a question.</h1>
    <p class="lede">
      Answers come with the numbers behind them, charts where they help, and the exact queries that produced them.
    </p>
    <ul>
      <li v-for="question in SUGGESTIONS" :key="question">
        <button type="button" @click="$emit('ask', question)">{{ question }}</button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.empty {
  padding: 12vh 0 2rem;
}

.kicker {
  font-family: var(--font-ui);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
}

h1 {
  font-family: var(--font-read);
  font-size: clamp(2rem, 5vw, 2.8rem);
  font-weight: 500;
  line-height: 1.1;
  letter-spacing: -0.01em;
  margin: 0.6rem 0 0.9rem;
}

.lede {
  font-family: var(--font-read);
  font-size: 1.1rem;
  color: var(--ink-secondary);
  max-width: 34rem;
}

ul {
  list-style: none;
  padding: 0;
  margin-top: 2rem;
  display: grid;
  gap: 0.5rem;
}

li {
  animation: rise 0.4s ease-out backwards;
}

li:nth-child(2) {
  animation-delay: 60ms;
}

li:nth-child(3) {
  animation-delay: 120ms;
}

li:nth-child(4) {
  animation-delay: 180ms;
}

button {
  font-family: var(--font-ui);
  font-size: 0.92rem;
  color: var(--ink);
  background: transparent;
  border: 1px solid var(--rule-strong);
  border-radius: 8px;
  padding: 0.65rem 0.9rem;
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition:
    border-color 0.15s,
    background 0.15s;
}

button:hover {
  border-color: var(--accent);
  background: var(--surface-raised);
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}
</style>

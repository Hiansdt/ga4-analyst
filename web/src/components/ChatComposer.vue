<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ busy: boolean }>()
const emit = defineEmits<{ ask: [question: string] }>()
const draft = ref('')

// TODO(ui-a11y): Add :focus-visible rings to the composer textarea and the Ask button
// WHY: the textarea removes its outline and only changes a 1px border color on focus
// DONE-WHEN: keyboard focus on the textarea and on the Ask button shows a ring with at least 3:1 contrast against the page
function submit(): void {
  const question = draft.value.trim()
  // While an answer streams the question would be ignored, so keep it in the box instead of losing it.
  if (!question || props.busy) return
  emit('ask', question)
  draft.value = ''
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <form class="composer" @submit.prevent="submit">
    <label class="visually-hidden" for="question">Ask a question about the store</label>
    <textarea
      id="question"
      v-model="draft"
      rows="1"
      placeholder="Ask about revenue, products, channels, conversion..."
      @keydown="onKeydown"
    />
    <button type="submit" :disabled="busy || !draft.trim()">{{ busy ? 'Answering' : 'Ask' }}</button>
  </form>
</template>

<style scoped>
.composer {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
  background: var(--surface-raised);
  border: 1px solid var(--rule-strong);
  border-radius: 10px;
  padding: 0.5rem;
  box-shadow: 0 8px 24px -12px rgb(11 11 11 / 0.18);
}

textarea {
  flex: 1;
  resize: none;
  field-sizing: content;
  max-height: 10rem;
  border: 0;
  outline: 0;
  background: transparent;
  font: inherit;
  font-family: var(--font-ui);
  font-size: 0.95rem;
  color: var(--ink);
  padding: 0.45rem 0.5rem;
}

button {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  font-weight: 600;
  color: #ffffff;
  background: var(--accent);
  border: 0;
  border-radius: 7px;
  padding: 0.55rem 1.1rem;
  cursor: pointer;
}

button:disabled {
  background: var(--rule-strong);
  cursor: default;
}

.composer:focus-within {
  border-color: var(--accent);
}
</style>

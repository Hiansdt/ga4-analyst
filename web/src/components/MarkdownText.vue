<script setup lang="ts">
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed } from 'vue'

// TODO(ui-a11y): Give the conversation an h1 and render model headings below the question level
// WHY: once a chat exists there is no h1, and model headings render as h2 like the questions, flattening the outline
// DONE-WHEN: the accessibility tree shows one h1, questions as h2 and answer headings as h3 or lower
const props = defineProps<{ text: string }>()

// Model output is untrusted: sanitize the rendered HTML before it reaches the page.
const html = computed(() => DOMPurify.sanitize(marked.parse(props.text, { async: false })))
</script>

<template>
  <div class="markdown" v-html="html" />
</template>

<style scoped>
.markdown {
  font-family: var(--font-read);
  font-size: 1.06rem;
  line-height: 1.65;
  color: var(--ink);
}

.markdown :deep(p) {
  margin: 0.6rem 0;
}

.markdown :deep(strong) {
  font-weight: 600;
}

.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3) {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 1.1rem 0 0.4rem;
}

.markdown :deep(ul),
.markdown :deep(ol) {
  padding-left: 1.25rem;
  margin: 0.5rem 0;
}

.markdown :deep(li) {
  margin: 0.3rem 0;
}

.markdown :deep(table) {
  border-collapse: collapse;
  font-family: var(--font-ui);
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
  margin: 0.9rem 0;
  display: block;
  overflow-x: auto;
}

.markdown :deep(th),
.markdown :deep(td) {
  padding: 0.35rem 1rem 0.35rem 0;
  border-bottom: 1px solid var(--rule);
  text-align: left;
}

.markdown :deep(th) {
  color: var(--ink-secondary);
  font-weight: 600;
}

.markdown :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.85em;
}
</style>

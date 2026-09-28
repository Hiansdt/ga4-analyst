// Owns the conversation state and its connection to the API. Components only read it and call ask/newChat.

import { ref } from 'vue'
import { askQuestion, ConversationGone, createConversation, loadConversation } from '../api/client'
import { applyEvent, newTurn, replayTurn, type Turn } from './turn'

const STORAGE_KEY = 'ga4-analyst.conversation'

export function useChat() {
  const turns = ref<Turn[]>([])
  const busy = ref(false)
  const notice = ref<string | null>(null)
  let conversationId: string | null = null

  async function restore(): Promise<void> {
    const saved = readSavedId()
    if (!saved) return
    try {
      turns.value = (await loadConversation(saved)).map(replayTurn)
      conversationId = saved
    } catch (error) {
      saveId(null)
      if (error instanceof ConversationGone) notice.value = 'Your previous chat expired, so this is a new one.'
    }
  }

  async function ask(question: string): Promise<void> {
    if (busy.value || !question.trim()) return
    busy.value = true
    notice.value = null
    turns.value.push(newTurn(question))
    const index = turns.value.length - 1
    const onEvent = (event: Parameters<typeof applyEvent>[1]) => {
      turns.value[index] = applyEvent(turns.value[index], event)
    }

    try {
      try {
        await askQuestion(await currentConversation(), question, onEvent)
      } catch (error) {
        if (!(error instanceof ConversationGone)) throw error
        // The server dropped an idle chat. Ask again in a fresh one; earlier answers are no longer in context.
        conversationId = null
        notice.value = 'This chat had expired, so the question was answered in a new chat without the earlier context.'
        await askQuestion(await currentConversation(), question, onEvent)
      }
      if (turns.value[index].status === 'streaming') fail(index, 'The connection closed before the answer finished.')
    } catch (error) {
      fail(index, error instanceof Error ? error.message : 'Something went wrong.')
    } finally {
      busy.value = false
    }
  }

  function newChat(): void {
    if (busy.value) return
    conversationId = null
    saveId(null)
    turns.value = []
    notice.value = null
  }

  async function currentConversation(): Promise<string> {
    if (!conversationId) {
      conversationId = await createConversation()
      saveId(conversationId)
    }
    return conversationId
  }

  function fail(index: number, message: string): void {
    turns.value[index] = { ...turns.value[index], status: 'failed', error: message }
  }

  return { turns, busy, notice, restore, ask, newChat }
}

// Remembering the chat across reloads is a convenience; storage can be unavailable (private mode).
function readSavedId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function saveId(id: string | null): void {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Not remembering the chat is acceptable.
  }
}

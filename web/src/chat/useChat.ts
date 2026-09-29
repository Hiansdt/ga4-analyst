// Owns one dataset's conversation state and its connection to the API. Components only read it and call ask/newChat.

import { ref } from 'vue'
import { askQuestion, ConversationGone, createConversation, loadConversation } from '../api/client'
import { applyEvent, newTurn, replayTurn, type Turn } from './turn'

// Each dataset remembers its own chat, so switching back to a dataset restores it.
const storageKey = (dataset: string) => `analyst.conversation.${dataset}`

export function useChat(dataset: string) {
  const turns = ref<Turn[]>([])
  const busy = ref(false)
  const notice = ref<string | null>(null)
  let conversationId: string | null = null

  // TODO(ui-harden): Keep the saved chat id when restoring fails for reasons other than expiry
  // WHY: any network or 5xx error during restore forgets the saved conversation for good
  // DONE-WHEN: with GET /api/conversations/{id} returning 500, the id stays in localStorage and a "Couldn't load your chat" notice with a retry is shown
  async function restore(): Promise<void> {
    const saved = readSavedId(dataset)
    if (!saved) return
    try {
      const conversation = await loadConversation(saved)
      if (conversation.dataset !== dataset) {
        saveId(dataset, null)
        return
      }
      turns.value = conversation.turns.map(replayTurn)
      conversationId = saved
    } catch (error) {
      saveId(dataset, null)
      if (error instanceof ConversationGone) notice.value = 'Your previous chat expired, so this is a new one.'
    }
  }

  // TODO(ui-harden): Add a Stop control that aborts the streaming answer
  // WHY: an answer takes about 20 seconds and costs money; a regretted question cannot be cancelled
  // DONE-WHEN: clicking Stop mid-answer cancels the fetch (visible in the network tab), marks the turn "Stopped" and re-enables the composer
  
  // TODO(ui-clarify): Mark a chat restart in the log with a persistent divider and dim the earlier turns
  // WHY: after an idle expiry, follow-ups lose their context while earlier turns still look live; the notice sits off-screen and clears on the next ask
  // DONE-WHEN: after forcing a 404 mid-chat, the log shows "Chat restarted after 15 minutes idle. Earlier questions are not in context." between turns, and earlier turns render dimmed
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
    saveId(dataset, null)
    turns.value = []
    notice.value = null
  }

  async function currentConversation(): Promise<string> {
    if (!conversationId) {
      conversationId = await createConversation(dataset)
      saveId(dataset, conversationId)
    }
    return conversationId
  }

  function fail(index: number, message: string): void {
    turns.value[index] = { ...turns.value[index], status: 'failed', error: message }
  }

  return { turns, busy, notice, restore, ask, newChat }
}

// Remembering the chat across reloads is a convenience; storage can be unavailable (private mode).
function readSavedId(dataset: string): string | null {
  try {
    return localStorage.getItem(storageKey(dataset))
  } catch {
    return null
  }
}

function saveId(dataset: string, id: string | null): void {
  try {
    if (id) localStorage.setItem(storageKey(dataset), id)
    else localStorage.removeItem(storageKey(dataset))
  } catch {
    // Not remembering the chat is acceptable.
  }
}

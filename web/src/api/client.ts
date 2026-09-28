import { SseParser } from './sse'
import type { AgentEvent, StoredTurn } from './types'

export class ConversationGone extends Error {}

export async function createConversation(): Promise<string> {
  const response = await fetch('/api/conversations', { method: 'POST' })
  if (!response.ok) throw new Error(`Could not start a conversation (${response.status})`)
  return (await response.json()).id
}

export async function loadConversation(id: string): Promise<StoredTurn[]> {
  const response = await fetch(`/api/conversations/${id}`)
  if (response.status === 404) throw new ConversationGone()
  if (!response.ok) throw new Error(`Could not load the conversation (${response.status})`)
  return (await response.json()).turns
}

/** Post a question and call onEvent for every event of the streamed answer. */
export async function askQuestion(id: string, question: string, onEvent: (event: AgentEvent) => void): Promise<void> {
  const response = await fetch(`/api/conversations/${id}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: question }),
  })
  if (response.status === 404) throw new ConversationGone()
  if (!response.ok || !response.body) throw new Error(`The question could not be sent (${response.status})`)

  const parser = new SseParser()
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    parser.push(value).forEach(onEvent)
  }
}

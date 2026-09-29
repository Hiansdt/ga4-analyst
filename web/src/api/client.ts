import { SseParser } from './sse'
import type { AgentEvent, DatasetInfo, StoredTurn } from './types'

export interface StoredConversation {
  dataset: string
  turns: StoredTurn[]
}

export class ConversationGone extends Error {}

// Error messages are shown to business users as is, so they carry no status codes.
const UNAVAILABLE = 'The analyst is unavailable right now. Please try again in a minute.'

export async function loadDatasets(): Promise<DatasetInfo[]> {
  return (await request('/api/datasets')).json()
}

export async function createConversation(dataset: string): Promise<string> {
  const response = await request('/api/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset }),
  })
  return (await response.json()).id
}

export async function loadConversation(id: string): Promise<StoredConversation> {
  return (await request(`/api/conversations/${id}`)).json()
}

/** Post a question and call onEvent for every event of the streamed answer. */
export async function askQuestion(id: string, question: string, onEvent: (event: AgentEvent) => void): Promise<void> {
  const response = await request(`/api/conversations/${id}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: question }),
  })
  if (!response.body) throw new Error(UNAVAILABLE)

  const parser = new SseParser()
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    parser.push(value).forEach(onEvent)
  }
}

async function request(url: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(url, init).catch(() => {
    throw new Error(UNAVAILABLE)
  })
  if (response.status === 404) throw new ConversationGone()
  // Limits (too many questions, a full chat) come with an explanation written for the user.
  if (response.status === 409 || response.status === 429) throw new Error(await explanation(response))
  if (!response.ok) throw new Error(UNAVAILABLE)
  return response
}

async function explanation(response: Response): Promise<string> {
  try {
    const { detail } = await response.json()
    return typeof detail === 'string' ? detail : UNAVAILABLE
  } catch {
    return UNAVAILABLE
  }
}

import { afterEach, describe, expect, it, vi } from 'vitest'
import { askQuestion, ConversationGone, createConversation, loadConversation } from './client'

const UNAVAILABLE = 'The analyst is unavailable right now. Please try again in a minute.'

function respondWith(status: number): void {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('Internal Server Error', { status })))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('client errors', () => {
  it('explains a server error in plain words', async () => {
    respondWith(500)

    await expect(askQuestion('abc', 'Q', () => {})).rejects.toThrow(UNAVAILABLE)
    await expect(createConversation()).rejects.toThrow(UNAVAILABLE)
    await expect(loadConversation('abc')).rejects.toThrow(UNAVAILABLE)
  })

  it('explains an unreachable server in plain words', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))

    await expect(askQuestion('abc', 'Q', () => {})).rejects.toThrow(UNAVAILABLE)
  })

  it.each([409, 429])('passes on the server explanation for a %i', async (status) => {
    const detail = 'Start a new chat to keep asking questions.'
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ detail }, { status })))

    await expect(askQuestion('abc', 'Q', () => {})).rejects.toThrow(detail)
  })

  it('reports an expired conversation separately', async () => {
    respondWith(404)

    await expect(askQuestion('abc', 'Q', () => {})).rejects.toBeInstanceOf(ConversationGone)
  })
})

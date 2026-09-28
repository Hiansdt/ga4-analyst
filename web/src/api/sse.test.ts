import { describe, expect, it } from 'vitest'
import { SseParser } from './sse'

describe('SseParser', () => {
  it('parses complete events into typed payloads', () => {
    const events = new SseParser().push('event: text_delta\ndata: {"text": "Hi"}\n\n')

    expect(events).toEqual([{ type: 'text_delta', text: 'Hi' }])
  })

  it('buffers events split across network chunks', () => {
    const parser = new SseParser()

    expect(parser.push('event: text_delta\nda')).toEqual([])
    expect(parser.push('ta: {"text": "Hi"}\n\nevent: turn_failed\n')).toEqual([{ type: 'text_delta', text: 'Hi' }])
    expect(parser.push('data: {"message": "x"}\n\n')).toEqual([{ type: 'turn_failed', message: 'x' }])
  })
})

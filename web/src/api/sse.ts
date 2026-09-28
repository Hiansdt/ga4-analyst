import type { AgentEvent } from './types'

/** Incremental Server-Sent Events parser. EventSource only supports GET, so the POST stream is parsed by hand. */
export class SseParser {
  private buffer = ''

  push(chunk: string): AgentEvent[] {
    this.buffer += chunk
    const blocks = this.buffer.split('\n\n')
    this.buffer = blocks.pop() ?? '' // the last piece may be an incomplete event
    return blocks.filter((block) => block.trim()).map(parseBlock)
  }
}

function parseBlock(block: string): AgentEvent {
  let type = ''
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) type = line.slice('event: '.length)
    else if (line.startsWith('data: ')) data += line.slice('data: '.length)
  }
  return { type, ...JSON.parse(data) } as AgentEvent
}

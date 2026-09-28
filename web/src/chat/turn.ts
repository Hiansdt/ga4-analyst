// One question and its answer as the UI shows it, built by folding agent events in order.
// Live streaming and reloaded conversations both go through applyEvent.

import type { AgentEvent, ChartSpec, Column, QueryDisplay, Row, StoredTurn } from '../api/types'

export type Block =
  | { kind: 'text'; text: string }
  | {
      kind: 'query'
      id: string
      sql: string
      status: 'running' | 'done' | 'failed'
      columns?: Column[]
      rows?: Row[]
      totalRows?: number
      error?: string
    }
  | { kind: 'chart'; id: string; chart: ChartSpec }
  | { kind: 'pending'; id: string; name: string }

export interface Turn {
  question: string
  blocks: Block[]
  status: 'streaming' | 'done' | 'failed'
  error?: string
}

export function newTurn(question: string): Turn {
  return { question, blocks: [], status: 'streaming' }
}

export function applyEvent(turn: Turn, event: AgentEvent): Turn {
  switch (event.type) {
    case 'text_delta': {
      const last = turn.blocks.at(-1)
      if (last?.kind === 'text') {
        return { ...turn, blocks: [...turn.blocks.slice(0, -1), { kind: 'text', text: last.text + event.text }] }
      }
      return { ...turn, blocks: [...turn.blocks, { kind: 'text', text: event.text }] }
    }
    case 'tool_started': {
      const block: Block =
        event.name === 'run_sql'
          ? { kind: 'query', id: event.tool_use_id, sql: String(event.input.sql ?? ''), status: 'running' }
          : { kind: 'pending', id: event.tool_use_id, name: event.name }
      return { ...turn, blocks: [...turn.blocks, block] }
    }
    case 'tool_finished':
      return { ...turn, blocks: turn.blocks.flatMap((block) => finishBlock(block, event)) }
    case 'turn_failed':
      return { ...turn, status: 'failed', error: event.message }
    case 'turn_completed':
      return turn.status === 'failed' ? turn : { ...turn, status: 'done' }
  }
}

function finishBlock(block: Block, event: Extract<AgentEvent, { type: 'tool_finished' }>): Block[] {
  if (!('id' in block) || block.id !== event.tool_use_id) return [block]
  if (block.kind === 'query') {
    const display = event.display as QueryDisplay
    return event.is_error
      ? [{ ...block, status: 'failed', error: display.error }]
      : [{ ...block, status: 'done', columns: display.columns, rows: display.rows, totalRows: display.total_rows }]
  }
  // A chart that failed validation is the model's to fix; the user only sees the chart it then makes.
  return event.is_error ? [] : [{ kind: 'chart', id: block.id, chart: event.display as ChartSpec }]
}

export function replayTurn(stored: StoredTurn): Turn {
  const turn = stored.events.reduce(applyEvent, newTurn(stored.question))
  return turn.status === 'streaming' ? { ...turn, status: 'done' } : turn
}

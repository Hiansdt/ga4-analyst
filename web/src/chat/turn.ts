// One question and its answer as the UI shows it, built by folding agent events in order.
// Live streaming and reloaded conversations both go through applyEvent.

import type { AgentEvent, ChartSpec, Column, FollowUpsDisplay, QueryDisplay, Row, StoredTurn } from '../api/types'

export type Block =
  | { kind: 'text'; text: string }
  | {
      kind: 'query'
      id: string
      label?: string // what the query computes, in plain words
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
  followUps?: string[] // next questions the model suggested, shown as buttons
}

// Tools whose results are query steps. query_metrics writes its SQL on the server, so it arrives when the step finishes.
const QUERY_TOOLS = new Set(['run_sql', 'query_metrics'])
// Suggestions belong to the turn, not to its steps.
const FOLLOW_UPS_TOOL = 'suggest_follow_ups'

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
      if (event.name === FOLLOW_UPS_TOOL) return turn
      const block: Block =
        QUERY_TOOLS.has(event.name)
          ? {
              kind: 'query',
              id: event.tool_use_id,
              label: typeof event.input.purpose === 'string' ? event.input.purpose : undefined,
              sql: String(event.input.sql ?? ''),
              status: 'running',
            }
          : { kind: 'pending', id: event.tool_use_id, name: event.name }
      return { ...turn, blocks: [...turn.blocks, block] }
    }
    case 'tool_finished':
      if (event.name === FOLLOW_UPS_TOOL) {
        return event.is_error ? turn : { ...turn, followUps: (event.display as FollowUpsDisplay).questions }
      }
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
    const settled = { ...block, label: display.label ?? block.label, sql: display.sql ?? block.sql }
    return event.is_error
      ? [{ ...settled, status: 'failed', error: display.error }]
      : [{ ...settled, status: 'done', columns: display.columns, rows: display.rows, totalRows: display.total_rows }]
  }
  // A chart that failed validation is the model's to fix; the user only sees the chart it then makes.
  return event.is_error ? [] : [{ kind: 'chart', id: block.id, chart: event.display as ChartSpec }]
}

// Text written before a query is the model narrating its steps. Text followed only by charts is the answer,
// since the model often writes it before drawing the chart.
export function isNarration(blocks: Block[], index: number): boolean {
  return blocks.slice(index + 1).some((block) => block.kind === 'query')
}

export function replayTurn(stored: StoredTurn): Turn {
  const turn = stored.events.reduce(applyEvent, newTurn(stored.question))
  return turn.status === 'streaming' ? { ...turn, status: 'done' } : turn
}

import { describe, expect, it } from 'vitest'
import type { AgentEvent } from '../api/types'
import { applyEvent, type Block, isNarration, newTurn, replayTurn } from './turn'

const apply = (events: AgentEvent[]) => events.reduce(applyEvent, newTurn('Q'))

describe('applyEvent', () => {
  it('joins consecutive text deltas into one text block', () => {
    const turn = apply([
      { type: 'text_delta', text: 'Revenue ' },
      { type: 'text_delta', text: 'was $1.' },
    ])

    expect(turn.blocks).toEqual([{ kind: 'text', text: 'Revenue was $1.' }])
  })

  it('tracks a query step from start to finish', () => {
    const started = apply([{ type: 'tool_started', tool_use_id: 'a', name: 'run_sql', input: { sql: 'SELECT 1' } }])
    expect(started.blocks).toEqual([{ kind: 'query', id: 'a', sql: 'SELECT 1', status: 'running' }])

    const finished = applyEvent(started, {
      type: 'tool_finished',
      tool_use_id: 'a',
      name: 'run_sql',
      is_error: false,
      display: { sql: 'SELECT 1', columns: [{ name: 'n', type: 'INTEGER' }], rows: [{ n: 1 }], total_rows: 1 },
    })
    expect(finished.blocks[0]).toMatchObject({ status: 'done', totalRows: 1, rows: [{ n: 1 }] })
  })

  it('shows a metrics query as a query step with the SQL generated for it', () => {
    const turn = apply([
      { type: 'tool_started', tool_use_id: 'm', name: 'query_metrics', input: { metrics: ['revenue'] } },
      {
        type: 'tool_finished',
        tool_use_id: 'm',
        name: 'query_metrics',
        is_error: false,
        display: { sql: 'WITH orders AS (...)', columns: [{ name: 'revenue', type: 'FLOAT' }], rows: [], total_rows: 1 },
      },
    ])

    expect(turn.blocks).toEqual([
      expect.objectContaining({ kind: 'query', status: 'done', sql: 'WITH orders AS (...)', totalRows: 1 }),
    ])
  })

  it('keeps failed queries visible with their error', () => {
    const turn = apply([
      { type: 'tool_started', tool_use_id: 'a', name: 'run_sql', input: { sql: 'SELEC' } },
      {
        type: 'tool_finished',
        tool_use_id: 'a',
        name: 'run_sql',
        is_error: true,
        display: { sql: 'SELEC', error: 'Syntax error' },
      },
    ])

    expect(turn.blocks[0]).toMatchObject({ status: 'failed', error: 'Syntax error' })
  })

  it('turns a finished chart call into a chart block', () => {
    const chart = { type: 'line', title: 'Daily', x: 'day', y: ['revenue'], rows: [{ day: '2020-12-01', revenue: 5 }] }
    const turn = apply([
      { type: 'tool_started', tool_use_id: 'c', name: 'create_chart', input: {} },
      { type: 'tool_finished', tool_use_id: 'c', name: 'create_chart', is_error: false, display: chart } as AgentEvent,
    ])

    expect(turn.blocks).toEqual([{ kind: 'chart', id: 'c', chart }])
  })

  it('starts a new text block after a tool step', () => {
    const turn = apply([
      { type: 'text_delta', text: 'Let me check.' },
      { type: 'tool_started', tool_use_id: 'a', name: 'run_sql', input: { sql: 'SELECT 1' } },
      { type: 'text_delta', text: 'Done.' },
    ])

    expect(turn.blocks.map((b) => b.kind)).toEqual(['text', 'query', 'text'])
  })

  it('marks the turn done or failed', () => {
    expect(apply([{ type: 'turn_completed', usage: {} as never }]).status).toBe('done')
    expect(apply([{ type: 'turn_failed', message: 'API down' }])).toMatchObject({ status: 'failed', error: 'API down' })
  })

  it('does not mutate the previous turn', () => {
    const before = newTurn('Q')

    applyEvent(before, { type: 'text_delta', text: 'x' })

    expect(before.blocks).toEqual([])
  })
})

describe('replayTurn', () => {
  it('rebuilds a stored turn as a completed turn', () => {
    const turn = replayTurn({ question: 'Hi', events: [{ type: 'text_delta', text: 'Hello.' }] })

    expect(turn).toMatchObject({ question: 'Hi', status: 'done', blocks: [{ kind: 'text', text: 'Hello.' }] })
  })
})

describe('isNarration', () => {
  const text: Block = { kind: 'text', text: 'x' }
  const query: Block = { kind: 'query', id: 'q', sql: 'SELECT 1', status: 'done' }
  const chart: Block = { kind: 'chart', id: 'c', chart: { type: 'line', title: 't', x: 'd', y: ['r'], rows: [] } }
  const pending: Block = { kind: 'pending', id: 'p', name: 'create_chart' }

  it('marks text written before a query as narration', () => {
    expect(isNarration([text, query, text], 0)).toBe(true)
  })

  it('treats text followed only by charts as the answer', () => {
    expect(isNarration([text, chart], 0)).toBe(false)
    expect(isNarration([text, pending], 0)).toBe(false)
    expect(isNarration([text, query, text, chart], 2)).toBe(false)
  })

  it('treats the last text as the answer', () => {
    expect(isNarration([text, query, text], 2)).toBe(false)
  })
})

// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Block } from '../chat/turn'
import QueryStep from './QueryStep.vue'

type QueryBlock = Extract<Block, { kind: 'query' }>

const summary = (step: Partial<QueryBlock>) =>
  mount(QueryStep, { props: { step: { kind: 'query', id: 'a', sql: 'SELECT 1', status: 'done', ...step } } })
    .get('summary')
    .text()

describe('QueryStep summary', () => {
  it('uses the singular for one row', () => {
    expect(summary({ totalRows: 1 })).toBe('Queried the data, 1 row')
  })

  it('formats large row counts', () => {
    expect(summary({ totalRows: 2304 })).toBe('Queried the data, 2,304 rows')
  })

  it('leaves out the count when the total is missing', () => {
    expect(summary({})).toBe('Queried the data')
  })
  it('names the step by what it computed', () => {
    expect(summary({ label: 'Revenue by month', totalRows: 3 })).toBe('Revenue by month, 3 rows')
    expect(summary({ label: 'Revenue by month', status: 'running' })).toBe('Revenue by month')
  })
})

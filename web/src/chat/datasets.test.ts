import { describe, expect, it } from 'vitest'
import type { DatasetInfo } from '../api/types'
import { pickDataset } from './datasets'

const info = (id: string): DatasetInfo => ({ id, name: id, start: '2020-01-01', end: '2020-12-31', example_questions: [] })
const available = [info('ga4'), info('thelook')]

describe('pickDataset', () => {
  it('opens the dataset a link asks for', () => {
    expect(pickDataset('?dataset=thelook', available)).toBe('thelook')
  })

  it('falls back to the first dataset for a missing or unknown one', () => {
    expect(pickDataset('', available)).toBe('ga4')
    expect(pickDataset('?dataset=weather', available)).toBe('ga4')
  })
})

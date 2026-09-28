import { describe, expect, it } from 'vitest'
import type { ChartSpec } from '../api/types'
import { buildOption, formatValue, valueKind } from './options'

const spec = (overrides: Partial<ChartSpec>): ChartSpec => ({
  type: 'line',
  title: 'T',
  x: 'day',
  y: ['revenue'],
  rows: [
    { day: '2020-12-01', revenue: 100 },
    { day: '2020-12-02', revenue: 250 },
  ],
  ...overrides,
})

describe('valueKind and formatValue', () => {
  it('infers the unit from the column name', () => {
    expect(valueKind('revenue', [1])).toBe('currency')
    expect(valueKind('conversion_rate_pct', [1.4])).toBe('percent')
    expect(valueKind('conversion_rate', [0.014])).toBe('ratio')
    expect(valueKind('orders', [3])).toBe('number')
  })

  it('formats each kind for business readers', () => {
    expect(formatValue(158166, 'currency')).toBe('$158,166')
    expect(formatValue(68.654, 'currency')).toBe('$68.65')
    expect(formatValue(1.393, 'percent')).toBe('1.4%')
    expect(formatValue(0.01393, 'ratio')).toBe('1.4%')
    expect(formatValue(2304, 'number')).toBe('2,304')
  })
})

describe('buildOption', () => {
  it('draws one line per y column over the x labels', () => {
    const option = buildOption(spec({}))

    expect(option.xAxis).toMatchObject({ type: 'category', data: ['Dec 1', 'Dec 2'] })
    expect(option.series).toMatchObject([{ type: 'line', name: 'revenue', data: [100, 250] }])
    expect(option.legend).toMatchObject({ show: false })
  })

  it('shows a legend once there are several series', () => {
    const option = buildOption(
      spec({ type: 'bar', x: 'month', y: ['desktop', 'mobile'], rows: [{ month: 'Dec', desktop: 1, mobile: 2 }] }),
    )

    expect(option.series).toHaveLength(2)
    expect(option.legend).toMatchObject({ show: true })
  })

  it('orders funnel steps largest first, whatever order the query returned', () => {
    const option = buildOption(
      spec({
        type: 'funnel',
        x: 'step',
        y: ['users'],
        rows: [
          { step: 'Carted', users: 20 },
          { step: 'Purchased', users: 5 },
          { step: 'Viewed', users: 100 },
        ],
      }),
    )
    const [series] = option.series as { data: { name: string }[]; label: { position: string } }[]

    expect(series.data.map((d) => d.name)).toEqual(['Viewed', 'Carted', 'Purchased'])
    expect(series.label.position).toBe('right') // narrow steps can't fit their label inside
  })

  it('folds pie slices past the fifth into Other', () => {
    const rows = ['a', 'b', 'c', 'd', 'e', 'f', 'g'].map((name, i) => ({ channel: name, revenue: 70 - i * 10 }))
    const option = buildOption(spec({ type: 'pie', x: 'channel', y: ['revenue'], rows }))
    const [series] = option.series as { data: { name: string; value: number }[] }[]

    expect(series.data.map((d) => d.name)).toEqual(['a', 'b', 'c', 'd', 'e', 'Other'])
    expect(series.data.at(-1)?.value).toBe(20 + 10)
  })
})

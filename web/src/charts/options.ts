// Chart spec (from the create_chart tool) to an ECharts option. Pure, so it is unit tested.
// Colors follow the validated reference palette: categorical slots in fixed order, an ordinal
// blue ramp for funnel steps, text in ink tokens rather than series colors.

import type { EChartsOption } from 'echarts'
import type { ChartSpec, Row } from '../api/types'

const INK = { primary: '#0b0b0b', secondary: '#52514e', grid: '#e6e5e1', surface: '#fcfcfb' }
const CATEGORICAL = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']
const OTHER = '#a8a7a2'
const FUNNEL_RAMP = ['#104281', '#1c5cab', '#2a78d6', '#5598e7', '#86b6ef'] // darkest first; stops at step 250
const MAX_PIE_SLICES = 5

export type ValueKind = 'currency' | 'percent' | 'ratio' | 'number'

export function valueKind(column: string, values: number[]): ValueKind {
  const name = column.toLowerCase()
  if (/revenue|sales|amount|price|value|aov|spend/.test(name)) return 'currency'
  if (/pct|percent/.test(name)) return 'percent'
  if (/rate|share|ratio/.test(name)) return values.every((v) => Math.abs(v) <= 1) ? 'ratio' : 'percent'
  return 'number'
}

export function formatValue(value: number | null | undefined, kind: ValueKind): string {
  if (value === null || value === undefined) return 'n/a'
  switch (kind) {
    case 'currency':
      return value.toLocaleString('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: Math.abs(value) >= 100 ? 0 : 2,
      })
    case 'percent':
      return `${value.toFixed(1)}%`
    case 'ratio':
      return `${(value * 100).toFixed(1)}%`
    case 'number':
      return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
}

function formatLabel(value: Row[string]): string {
  const text = String(value ?? '')
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return new Date(`${text}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
  }
  if (/^\d{4}-\d{2}$/.test(text)) {
    return new Date(`${text}-01T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' })
  }
  return text
}

const numbersOf = (rows: Row[], column: string) => rows.map((row) => Number(row[column] ?? 0))

const tooltip = { backgroundColor: '#ffffff', borderColor: INK.grid, textStyle: { color: INK.primary } }

export function buildOption(spec: ChartSpec): EChartsOption {
  if (spec.type === 'funnel' || spec.type === 'pie') return buildSingleSeries(spec)

  const kinds = spec.y.map((column) => valueKind(column, numbersOf(spec.rows, column)))
  const format = (value: number, index = 0) => formatValue(value, kinds[index] ?? kinds[0])
  const multiple = spec.y.length > 1

  return {
    color: CATEGORICAL,
    textStyle: { fontFamily: 'inherit', color: INK.secondary },
    grid: { left: 8, right: 16, top: multiple ? 40 : 16, bottom: 8, containLabel: true },
    legend: { show: multiple, top: 0, left: 0, icon: 'roundRect', textStyle: { color: INK.secondary } },
    tooltip: {
      ...tooltip,
      trigger: 'axis',
      axisPointer: { type: spec.type === 'line' ? 'line' : 'shadow' },
      valueFormatter: (value) => format(Number(value)),
    },
    xAxis: {
      type: 'category',
      data: spec.rows.map((row) => formatLabel(row[spec.x])),
      axisLine: { lineStyle: { color: INK.grid } },
      axisTick: { show: false },
      axisLabel: { color: INK.secondary, hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: INK.secondary, formatter: (value: number) => format(value) },
      splitLine: { lineStyle: { color: INK.grid } },
    },
    series: spec.y.map((column) =>
      spec.type === 'line'
        ? {
            type: 'line',
            name: column,
            data: numbersOf(spec.rows, column),
            showSymbol: false,
            symbolSize: 8,
            lineStyle: { width: 2 },
          }
        : {
            type: 'bar',
            name: column,
            data: numbersOf(spec.rows, column),
            barMaxWidth: 40,
            itemStyle: { borderRadius: [4, 4, 0, 0] },
          },
    ),
  }
}

function buildSingleSeries(spec: ChartSpec): EChartsOption {
  const [column] = spec.y
  const kind = valueKind(column, numbersOf(spec.rows, column))
  let data = spec.rows.map((row) => ({ name: formatLabel(row[spec.x]), value: Number(row[column] ?? 0) }))

  if (spec.type === 'funnel') {
    // Funnels are closed (each step is a subset of the previous one), so size order is step order,
    // whatever order the query returned the rows in.
    const steps = [...data].sort((a, b) => b.value - a.value)
    return {
      tooltip: { ...tooltip, trigger: 'item', valueFormatter: (value) => formatValue(Number(value), kind) },
      series: [
        {
          type: 'funnel',
          sort: 'none',
          gap: 2,
          left: 0,
          top: 8,
          bottom: 8,
          width: '58%',
          minSize: '6%',
          // Narrow steps can't fit a label inside, so labels sit to the right in ink colors.
          label: {
            position: 'right',
            color: INK.primary,
            formatter: ({ name, value }) => `${name}  ${formatValue(Number(value), kind)}`,
          },
          labelLine: { lineStyle: { color: INK.grid } },
          itemStyle: { borderColor: INK.surface, borderWidth: 2 },
          data: steps.map((d, i) => ({ ...d, itemStyle: { color: FUNNEL_RAMP[Math.min(i, FUNNEL_RAMP.length - 1)] } })),
        },
      ],
    }
  }

  if (data.length > MAX_PIE_SLICES + 1) {
    const rest = data.slice(MAX_PIE_SLICES).reduce((sum, d) => sum + d.value, 0)
    data = [...data.slice(0, MAX_PIE_SLICES), { name: 'Other', value: rest }]
  }
  return {
    color: [...CATEGORICAL.slice(0, Math.min(data.length, MAX_PIE_SLICES)), OTHER],
    tooltip: { ...tooltip, trigger: 'item', valueFormatter: (value) => formatValue(Number(value), kind) },
    legend: { show: true, bottom: 0, icon: 'roundRect', textStyle: { color: INK.secondary } },
    series: [
      {
        type: 'pie',
        radius: ['45%', '72%'],
        center: ['50%', '45%'],
        itemStyle: { borderColor: INK.surface, borderWidth: 2, borderRadius: 4 },
        label: { color: INK.secondary, formatter: '{d}%' },
        data,
      },
    ],
  }
}

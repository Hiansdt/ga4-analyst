// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import DatasetSwitcher from './DatasetSwitcher.vue'

const datasets = [
  { id: 'ga4', name: 'Google Merchandise Store', start: '2020-11-01', end: '2021-01-31', example_questions: [] },
  { id: 'thelook', name: 'TheLook Fashion Store', start: '2019-01-01', end: '2026-09-27', example_questions: [] },
]

describe('DatasetSwitcher', () => {
  it('offers every dataset as a choice with the current one selected', () => {
    const view = mount(DatasetSwitcher, { props: { datasets, selected: 'ga4', disabled: false } })
    const radios = view.findAll<HTMLInputElement>('input[type="radio"]')

    expect(view.text()).toContain('TheLook Fashion Store')
    expect(radios.map((radio) => radio.element.checked)).toEqual([true, false])
  })

  it('switches when another dataset is chosen', async () => {
    const view = mount(DatasetSwitcher, { props: { datasets, selected: 'ga4', disabled: false } })

    await view.findAll('input[type="radio"]')[1].setValue(true)

    expect(view.emitted('select')).toEqual([['thelook']])
  })

  it('cannot switch while an answer is streaming', () => {
    const view = mount(DatasetSwitcher, { props: { datasets, selected: 'ga4', disabled: true } })

    expect(view.get('fieldset').attributes('disabled')).toBeDefined()
  })
})

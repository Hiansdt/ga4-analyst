// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import EmptyState from './EmptyState.vue'

const dataset = {
  name: 'Google Merchandise Store',
  start: '2020-11-01',
  end: '2021-01-31',
  example_questions: ['How are we doing?', 'Where do customers drop off before buying?'],
}

describe('EmptyState', () => {
  it('introduces the dataset and its period', () => {
    const view = mount(EmptyState, { props: { dataset } })

    expect(view.get('.kicker').text()).toBe('Google Merchandise Store, Nov 2020 to Jan 2021')
  })

  it("asks one of the dataset's example questions when it is clicked", async () => {
    const view = mount(EmptyState, { props: { dataset } })

    await view.findAll('li button')[1].trigger('click')

    expect(view.emitted('ask')).toEqual([['Where do customers drop off before buying?']])
  })

  it('still invites a question before the dataset has loaded', () => {
    const view = mount(EmptyState, { props: { dataset: null } })

    expect(view.find('h1').exists()).toBe(true)
    expect(view.findAll('li')).toHaveLength(0)
  })
})

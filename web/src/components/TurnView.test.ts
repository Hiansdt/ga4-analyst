// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Turn } from '../chat/turn'
import TurnView from './TurnView.vue'

const turn: Turn = {
  question: 'Where do customers drop off?',
  blocks: [{ kind: 'text', text: 'Mostly between viewing and adding to cart.' }],
  status: 'done',
  followUps: ['Break down cart drop-off by device', 'Compare December with January'],
}

describe('TurnView follow-ups', () => {
  it('asks a suggested question when it is clicked', async () => {
    const view = mount(TurnView, { props: { turn, showFollowUps: true } })

    await view.get('.follow-ups button').trigger('click')

    expect(view.emitted('ask')).toEqual([['Break down cart drop-off by device']])
  })

  it('hides suggestions on earlier turns', () => {
    const view = mount(TurnView, { props: { turn, showFollowUps: false } })

    expect(view.find('.follow-ups').exists()).toBe(false)
  })
})

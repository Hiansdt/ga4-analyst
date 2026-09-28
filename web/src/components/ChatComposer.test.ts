// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatComposer from './ChatComposer.vue'

describe('ChatComposer', () => {
  it('asks and clears the draft on Enter', async () => {
    const composer = mount(ChatComposer, { props: { busy: false } })
    const textarea = composer.get('textarea')

    await textarea.setValue('Revenue in December?')
    await textarea.trigger('keydown', { key: 'Enter' })

    expect(composer.emitted('ask')).toEqual([['Revenue in December?']])
    expect(textarea.element.value).toBe('')
  })

  it('keeps the draft when Enter is pressed while an answer is streaming', async () => {
    const composer = mount(ChatComposer, { props: { busy: true } })
    const textarea = composer.get('textarea')

    await textarea.setValue('next')
    await textarea.trigger('keydown', { key: 'Enter' })

    expect(composer.emitted('ask')).toBeUndefined()
    expect(textarea.element.value).toBe('next')
  })
})

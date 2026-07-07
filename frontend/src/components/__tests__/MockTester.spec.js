import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MockTester from '../MockTester.vue'

function factory(path = '/products/{id}') {
  return mount(MockTester, {
    props: {
      endpoint: { method: 'GET', path, request_example: {} },
      baseUrl: 'http://test/m/shop',
    },
  })
}

describe('MockTester path params', () => {
  it('shows an input per path param and disables send until filled', async () => {
    const wrapper = factory()
    const input = wrapper.find('#param-id')
    expect(input.exists()).toBe(true)

    const send = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Send'))
    expect(send.attributes('disabled')).toBeDefined()

    await input.setValue('7')
    expect(send.attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('http://test/m/shop/products/7')
  })

  it('has no param inputs and enabled send for plain paths', () => {
    const wrapper = factory('/products')
    expect(wrapper.find('#param-id').exists()).toBe(false)
    const send = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Send'))
    expect(send.attributes('disabled')).toBeUndefined()
  })
})

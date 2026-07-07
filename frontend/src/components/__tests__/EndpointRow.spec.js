import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import EndpointRow from '../EndpointRow.vue'

vi.mock('../../api/client', () => ({
  default: {},
  API_BASE: 'http://test',
}))

const endpoint = {
  id: 1,
  method: 'GET',
  path: '/users/42',
  status_code: 200,
  delay_ms: 150,
  error_rate: 25,
}

function factory() {
  return mount(EndpointRow, {
    props: { endpoint, baseUrl: 'http://test/m/shop-abc' },
  })
}

describe('EndpointRow', () => {
  it('renders method, path, status, delay and error rate', () => {
    const text = factory().text()
    expect(text).toContain('GET')
    expect(text).toContain('/users/42')
    expect(text).toContain('200')
    expect(text).toContain('150ms')
    expect(text).toContain('25% errors')
  })

  it('emits edit and delete', async () => {
    const wrapper = factory()
    const buttons = wrapper.findAll('button')
    await buttons.at(-2).trigger('click')
    await buttons.at(-1).trigger('click')
    expect(wrapper.emitted('edit')).toHaveLength(1)
    expect(wrapper.emitted('delete')).toHaveLength(1)
  })
})

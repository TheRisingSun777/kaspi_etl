import { describe, it, expect } from 'vitest'
import { POST as runPost } from '@/app/api/pricebot/run/route'

describe('route /api/pricebot/run', () => {
  it('returns proposal in dry mode', async () => {
    const body = { storeId: 'test-store', sku: 'SKU_TEST', ourPrice: 1234, dry: true }
    const req = new Request('http://localhost/api/pricebot/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    const res = await runPost(req)
    expect(res.ok).toBe(true)
    const js: any = await res.json()
    expect(js.ok).toBe(true)
    expect(js.dry).toBe(true)
    expect(typeof js.proposal?.targetPrice).toBe('number')
  })

  it('validates input and returns bad_input when missing fields', async () => {
    const req = new Request('http://localhost/api/pricebot/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
    const res = await runPost(req)
    expect(res.status).toBe(400)
    const js: any = await res.json()
    expect(js.ok).toBe(false)
    expect(js.code).toBe('bad_input')
  })
})



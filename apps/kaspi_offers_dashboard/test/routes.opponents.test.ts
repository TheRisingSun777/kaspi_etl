import { describe, it, expect } from 'vitest'
import { GET as opponentsGet } from '@/app/api/pricebot/opponents/route'

describe('route /api/pricebot/opponents', () => {
  it('returns ok payload even without productId', async () => {
    const req = new Request('http://localhost/api/pricebot/opponents?productId=&cityId=710000000')
    const res = await opponentsGet(req)
    expect(res.ok).toBe(true)
    const js: any = await res.json()
    expect(js.ok).toBe(true)
  })
})



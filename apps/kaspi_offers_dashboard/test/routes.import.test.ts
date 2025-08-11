import { describe, it, expect } from 'vitest'
import { POST as importPost } from '@/app/api/pricebot/import/route'

describe('route /api/pricebot/import (preview)', () => {
  it('parses CSV in dryRun mode and returns sample', async () => {
    const csv = 'sku,min_price,max_price,step,pricebot_status\nSKU1,100,200,1,on\nSKU2,0,0,2,off\n'
    const req = new Request('http://localhost/api/pricebot/import?dryRun=true', { method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: csv })
    const res = await importPost(req)
    expect(res.ok).toBe(true)
    const js: any = await res.json()
    expect(js.ok).toBe(true)
    expect(js.dryRun).toBe(true)
    expect(typeof js.total).toBe('number')
  })
})



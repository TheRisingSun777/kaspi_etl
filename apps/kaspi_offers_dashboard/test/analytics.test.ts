import { describe, it, expect } from 'vitest'
import { computeGlobalAnalytics } from '@/lib/analytics'
import type { AnalyzeResult } from '@/lib/types'

describe('analytics', () => {
  it('computes spreads and derived metrics', () => {
    const input: AnalyzeResult = {
      masterProductId: 'X',
      cityId: '710000000',
      variants: [
        { productId: '1', label: 'A', sellersCount: 2, sellers: [ { name: 's1', price: 1000 }, { name: 's2', price: 1200 } ] },
        { productId: '2', label: 'B', sellersCount: 3, sellers: [ { name: 's1', price: 900 }, { name: 's3', price: 950 }, { name: 's4', price: 1100 } ] },
      ]
    }
    const out = computeGlobalAnalytics(input)
    expect(out.analytics?.maxSpread).toBeDefined()
    expect(out.uniqueSellers).toBe(4)
  })
})



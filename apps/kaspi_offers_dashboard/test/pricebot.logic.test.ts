import { describe, it, expect } from 'vitest'
import { computeTargetPrice, isBotDense } from '@/server/pricebot/logic'

describe('pricebot logic', () => {
  it('undercuts competitor within guardrails', () => {
    const out = computeTargetPrice({ ourPrice: 1200, minPrice: 1000, maxPrice: 2000, step: 50, competitors: [ { seller:'a', price: 1100 } ] })
    expect(out.target).toBe(1050)
  })
  it('matches when bot-dense', () => {
    const dense = isBotDense([{ price: 1100 }, { price: 1102 }, { price: 1099 }], 1100)
    expect(dense).toBe(true)
    const out = computeTargetPrice({ ourPrice: 1200, minPrice: 1000, maxPrice: 2000, step: 50, competitors: [ { seller:'a', price: 1100 }, { seller:'b', price:1102 }, { seller:'c', price:1099 } ] })
    expect(out.target).toBe(1099)
  })
})



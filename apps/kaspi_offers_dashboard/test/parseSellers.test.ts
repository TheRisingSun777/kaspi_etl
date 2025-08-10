import { describe, it, expect } from 'vitest'
import { parseSellersFromHtml } from '@/server/parse'

const SAMPLE = `
<table class="sellers-table"><tr>
  <td class="sellers-table__merchant-name">Shop A</td>
  <td class="sellers-table__price-cell-text">12 990 ₸</td>
  <td class="sellers-table__delivery-text">Доставка 12 сентября</td>
</tr></table>
`

describe('parseSellersFromHtml', () => {
  it('extracts seller, price and delivery', () => {
    const sellers = parseSellersFromHtml(SAMPLE)
    expect(sellers.length).toBeGreaterThan(0)
    expect(sellers[0].name).toMatch(/Shop A/i)
    expect(sellers[0].price).toBe(12990)
    expect(String(sellers[0].deliveryDate || '')).toMatch(/Доставка/)
  })
})



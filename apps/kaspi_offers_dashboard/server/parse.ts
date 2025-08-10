import type { Seller } from '@/lib/types'

// Very lightweight HTML parser using regex heuristics for our known structures.
// Intentionally avoids DOM dependencies to keep dev deps minimal.
export function parseSellersFromHtml(html: string): Seller[] {
  const sellers: Seller[] = []
  if (!html) return sellers

  // Normalize whitespace for regex scanning
  const text = html.replace(/\r|\n/g, ' ').replace(/\s+/g, ' ')

  // Split by potential row wrappers to reduce cross-talk
  const rowCandidates = text.split(/<(?:li|tr|div|article)[^>]*>/i).map(s => s.trim()).filter(Boolean)

  for (const chunk of rowCandidates) {
    // Price: find first long digit group, optionally with spaces (e.g. 12 990)
    const priceMatch = chunk.match(/(\d[\d\s]{3,})/)
    const price = priceMatch ? Number((priceMatch[1] || '').replace(/\s/g, '')) : NaN
    if (!Number.isFinite(price) || price <= 0) continue

    // Seller name candidates
    let name = ''
    const nameMatch =
      chunk.match(/sellers-table__merchant-name[^>]*>([^<]{2,100})</i) ||
      chunk.match(/data-merchant-name[^>]*>([^<]{2,100})</i) ||
      chunk.match(/<a[^>]*href=["']?[^"']*\/shop\/seller[^>]*>([^<]{2,100})</i) ||
      chunk.match(/merchant[^>]*name[^>]*>([^<]{2,100})</i)
    if (nameMatch) name = nameMatch[1].trim()
    if (!name) continue

    // Delivery
    let delivery = ''
    const delMatch =
      chunk.match(/sellers-table__delivery[^>]*>([^<]{2,120})</i) ||
      chunk.match(/sellers-table__delivery-text[^>]*>([^<]{2,120})</i) ||
      chunk.match(/delivery[^>]*>([^<]{2,120})</i)
    if (delMatch) delivery = delMatch[1].trim()

    sellers.push({ name, price, deliveryDate: delivery })
  }

  // Dedupe by name, keep lowest price and prefer non-empty delivery
  const map = new Map<string, Seller>()
  for (const s of sellers) {
    const key = s.name.toLowerCase()
    const cur = map.get(key)
    if (!cur) map.set(key, s)
    else {
      if (s.price < cur.price || (!cur.deliveryDate && s.deliveryDate)) map.set(key, s)
    }
  }
  return Array.from(map.values()).sort((a,b)=>a.price-b.price)
}



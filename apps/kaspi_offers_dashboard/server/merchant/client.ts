// server/merchant/client.ts
// Minimal merchant client with mock fallback. Adjust endpoints to your cluster if needed.

export type MerchantOffer = {
  variantProductId: string
  name: string
  price: number
  stock?: number
  category?: string
}

const DEFAULT_BASE = process.env.KASPI_MERCHANT_API_BASE || 'https://kaspi.kz/shop/api/v2'
const MERCHANT_ID = process.env.KASPI_MERCHANT_ID || '30141222'
const API_KEY = process.env.KASPI_MERCHANT_API_KEY || process.env.KASPI_TOKEN || ''

function buildHeaders() {
  const headers: Record<string,string> = {
    'Accept': 'application/vnd.api+json;charset=UTF-8',
    'User-Agent': 'KaspiOffersDashboard/1.0',
  }
  if (API_KEY) {
    headers['Authorization'] = `Bearer ${API_KEY}`
    headers['X-Auth-Token'] = API_KEY
  }
  return headers
}

export async function listActiveOffers(merchantId: string = MERCHANT_ID): Promise<MerchantOffer[]> {
  // Seed file fallback (lets you prefill offers when API access is not configured)
  try {
    const fs = await import('node:fs')
    const path = await import('node:path')
    const seedPath = path.join(process.cwd(), 'server', 'db', 'seed.offers.json')
    if (fs.existsSync(seedPath)) {
      const doc = JSON.parse(fs.readFileSync(seedPath, 'utf8'))
      if (Array.isArray(doc?.offers)) return doc.offers as MerchantOffer[]
    }
  } catch {}

  if (!API_KEY) {
    // Mock sample when no key available
    return [
      { variantProductId: '121207970', name: 'Rashguard Black XL', price: 12990, stock: 7 },
      { variantProductId: '108382478', name: 'Phone Case Red', price: 1990, stock: 20 },
    ]
  }
  // Try a few known endpoints (clusters differ). Return first success.
  const candidates = [
    `${DEFAULT_BASE}/products?page[number]=1&page[size]=50`,
    `${DEFAULT_BASE}/offers?page[number]=1&page[size]=50&filter[offers][merchantId]=${encodeURIComponent(merchantId)}`,
    `${DEFAULT_BASE}/merchant/${encodeURIComponent(merchantId)}/offers?page[number]=1&page[size]=50`,
  ]
  for (const url of candidates) {
    try {
      const res = await fetch(url, { headers: buildHeaders() })
      if (!res.ok) continue
      const json: any = await res.json().catch(()=>null)
      const data: any[] = Array.isArray(json?.data) ? json.data : Array.isArray(json) ? json : []
      if (!data.length) continue
      const items: MerchantOffer[] = data.map((p:any) => ({
        variantProductId: String(p?.id || p?.attributes?.id || p?.attributes?.productId || ''),
        name: String(p?.attributes?.name || p?.attributes?.title || ''),
        price: Number(p?.attributes?.price || p?.attributes?.minPrice || p?.attributes?.currentPrice || 0),
        stock: Number(p?.attributes?.available || p?.attributes?.stock || 0),
        category: String(p?.attributes?.category || ''),
      })).filter(x=>x.variantProductId && x.name)
      if (items.length) return items
    } catch { /* try next */ }
  }
  // Fallback: derive recent items from orders (last 14 days)
  try {
    const now = new Date()
    const from = new Date(Date.now() - 14*24*3600*1000)
    const toISO = now.toISOString()
    const fromISO = from.toISOString()
    const url = `${DEFAULT_BASE}/orders?filter[orders][creationDate][$ge]=${encodeURIComponent(fromISO)}&filter[orders][creationDate][$le]=${encodeURIComponent(toISO)}&page[number]=1&page[size]=50`
    const res = await fetch(url, { headers: buildHeaders() })
    if (res.ok) {
      const json: any = await res.json().catch(()=>null)
      const data: any[] = Array.isArray(json?.data) ? json.data : []
      const map = new Map<string, MerchantOffer>()
      for (const o of data) {
        const attrs = o?.attributes || {}
        const items: any[] = Array.isArray(attrs?.items) ? attrs.items : Array.isArray(attrs?.positions) ? attrs.positions : []
        for (const it of items) {
          const id = String(it?.productId || it?.sku || it?.id || '')
          const name = String(it?.name || it?.title || '')
          const price = Number(it?.unitPrice || it?.price || it?.totalPrice || 0)
          if (!id || !name || !price) continue
          if (!map.has(id)) map.set(id, { variantProductId: id, name, price, stock: undefined, category: undefined })
        }
      }
      if (map.size) return Array.from(map.values())
    }
  } catch {}
  return []
}

export async function updatePrice(variantProductId: string, newPrice: number): Promise<{ ok: boolean; status: number }>{
  if (!API_KEY) return { ok: true, status: 200 } // mock
  // Placeholder: send single price update using bulk endpoint shape
  const url = `${DEFAULT_BASE}/prices`
  const body = JSON.stringify({ data: [{ type: 'prices', id: variantProductId, attributes: { price: newPrice } }] })
  const res = await fetch(url, { method: 'PUT', headers: { ...buildHeaders(), 'Content-Type': 'application/json' }, body })
  return { ok: res.ok, status: res.status }
}

export async function updatePricesBulk(items: Array<{ variantProductId: string; price: number }>): Promise<{ ok: boolean; status: number }>{
  if (!API_KEY) return { ok: true, status: 200 } // mock
  const url = `${DEFAULT_BASE}/prices`
  const body = JSON.stringify({ data: items.map(i => ({ type: 'prices', id: i.variantProductId, attributes: { price: i.price } })) })
  const res = await fetch(url, { method: 'PUT', headers: { ...buildHeaders(), 'Content-Type': 'application/json' }, body })
  return { ok: res.ok, status: res.status }
}



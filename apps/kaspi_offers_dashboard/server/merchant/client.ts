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
  if (!API_KEY) {
    // Mock sample when no key available
    return [
      { variantProductId: '121207970', name: 'Rashguard Black XL', price: 12990, stock: 7 },
      { variantProductId: '108382478', name: 'Phone Case Red', price: 1990, stock: 20 },
    ]
  }
  // Placeholder: fetch small page of products and map to offers
  const url = `${DEFAULT_BASE}/products?page[number]=1&page[size]=50`
  const res = await fetch(url, { headers: buildHeaders() })
  if (!res.ok) return []
  const json = await res.json().catch(()=>({ data: [] }))
  const items: MerchantOffer[] = (json?.data || []).map((p:any) => ({
    variantProductId: String(p?.id || ''),
    name: String(p?.attributes?.name || ''),
    price: Number(p?.attributes?.price || 0),
    stock: Number(p?.attributes?.available || 0),
    category: String(p?.attributes?.category || ''),
  }))
  return items
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



import { NextResponse } from 'next/server'
import { getSettings } from '@/server/db/pricebot.settings'
import { mcFetch, getMerchantId } from '@/lib/kaspi/client'
import { getLastRun } from '@/server/db/pricebot.runs'

export const runtime = 'nodejs'

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const merchantId = String(searchParams.get('merchantId') || searchParams.get('storeId') || process.env.KASPI_MERCHANT_ID || '')
    const cityId = String(searchParams.get('cityId') || process.env.DEFAULT_CITY_ID || '710000000')

    // Read local settings to derive counts
    const st = getSettings(merchantId)
    const skuEntries = Object.entries(st.sku || {})
    const totalSKUs = skuEntries.length
    const activeSKUs = skuEntries.filter(([,v])=>!!v.active).length

    // Load current offers page for stock and competition heuristic
    let competingSKUs = 0
    let zeroStock = 0
    try {
      const m = getMerchantId()
      const res = await mcFetch(`/bff/offer-view/list?m=${m}&p=0&l=100&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`)
      const js = await res.json().catch(()=>null) as any
      const arr: any[] = Array.isArray(js?.items) ? js.items : Array.isArray(js?.data) ? js.data : Array.isArray(js?.content) ? js.content : []
      for (const o of arr) {
        const stock = pickStock(o)
        const opponents = Number(o.sellersCount || o.opponents || 0)
        if (stock <= 0) zeroStock++
        if (Number.isFinite(opponents) && opponents > 1) competingSKUs++
      }
    } catch {}

    // last run telemetry
    const last = getLastRun(merchantId)
    const lastRunCount = last?.count ?? null
    const lastRunAvgDelta = last?.avgDelta ?? null
    const winRate = null

    return NextResponse.json({ ok:true, stats: { totalSKUs, activeSKUs, zeroStock, competingSKUs, winRate, lastRunCount, lastRunAvgDelta, cityId, merchantId } })
  } catch (e:any) {
    return NextResponse.json({ ok:false, error:String(e?.message||e) }, { status: 500 })
  }
}

function pickStock(o: any): number {
  const keys = ['stock','stockTotal','availableAmount','freeBalance','quantity','qty','available']
  for (const k of keys) {
    const v = o?.[k]
    if (typeof v === 'number') return v
    if (typeof v === 'string' && v.trim() !== '') { const n = Number(v); if (Number.isFinite(n)) return n }
    if (typeof v === 'boolean') return v ? 1 : 0
  }
  const av = o?.availabilities?.[0]
  const nested = ['stockCount','availableAmount','freeBalance','quantity','qty','available']
  if (av) {
    for (const k of nested) {
      const v = av[k]
      if (typeof v === 'number') return v
      if (typeof v === 'string' && v.trim() !== '') { const n = Number(v); if (Number.isFinite(n)) return n }
      if (typeof v === 'boolean') return v ? 1 : 0
    }
  }
  return 0
}



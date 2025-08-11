import { NextResponse } from 'next/server'
import { getSettings } from '@/server/db/pricebot.settings'

export async function POST(req: Request) {
  try {
    const { storeId, merchantId, sku, ourPrice, opponents } = await req.json()
    const mId = String(storeId || merchantId || '')
    if (!mId || !sku) return NextResponse.json({ ok:false, error:'BAD_INPUT' }, { status:400 })
    const st = getSettings(mId)
    const item = st.sku[sku] || { active:false, minPrice:0, maxPrice:0, stepKzt:1, intervalMin:5, ignoredOpponents:[] }
    const ignoreSet = new Set([...(st.globalIgnoredOpponents||[]), ...((item.ignoredOpponents)||[])])
    const opp = (Array.isArray(opponents)? opponents:[]).filter((o:any)=>!ignoreSet.has(String(o.sellerId||o.merchantId||o.merchantUID||o.id)))
    opp.sort((a:any,b:any)=>Number(a.price||0)-Number(b.price||0))
    const best = opp[0]?.price
    const ceil = item.maxPrice && item.maxPrice>0? item.maxPrice : undefined
    const floor = item.minPrice && item.minPrice>0? item.minPrice : undefined
    let target = typeof best==='number'? best - (item.stepKzt||1) : ourPrice
    if (typeof floor==='number') target = Math.max(floor, target)
    if (typeof ceil==='number') target = Math.min(ceil, target)
    target = Math.max(0, Math.round(target))
    return NextResponse.json({ ok:true, proposal:{ price: target, reason: { bestOpponent: best, step: item.stepKzt, floor, ceil } } })
  } catch (e:any) {
    return NextResponse.json({ ok:false, error:String(e?.message||e) }, { status:500 })
  }
}



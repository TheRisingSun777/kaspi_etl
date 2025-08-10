import { NextResponse } from 'next/server'
import { mergedIgnoredForSku, getStore } from '@/server/db/pricebot.v2'

export async function POST(req: Request) {
  try {
    const { storeId, sku, ourPrice, opponents } = await req.json()
    if (!storeId || !sku) return NextResponse.json({ ok:false, error:'BAD_INPUT' }, { status:400 })
    const st = getStore(storeId)
    const s = st.bySku[sku] || { active:false, min:0, max:0, step:1, intervalMin:5, ignore:[] }
    const ignoreSet = new Set(mergedIgnoredForSku(storeId, sku))
    const opp = (Array.isArray(opponents)? opponents:[]).filter((o:any)=>!ignoreSet.has(String(o.sellerId||o.merchantId||o.merchantUID)))
    opp.sort((a:any,b:any)=>Number(a.price||0)-Number(b.price||0))
    const best = opp[0]?.price
    const ceil = s.max>0? s.max : undefined
    const floor = s.min>0? s.min : undefined
    let target = typeof best==='number'? best - (s.step||1) : ourPrice
    if (typeof floor==='number') target = Math.max(floor, target)
    if (typeof ceil==='number') target = Math.min(ceil, target)
    target = Math.max(0, Math.round(target))
    return NextResponse.json({ ok:true, proposal:{ price: target, reason: { bestOpponent: best, step: s.step, floor, ceil } } })
  } catch (e:any) {
    return NextResponse.json({ ok:false, error:String(e?.message||e) }, { status:500 })
  }
}



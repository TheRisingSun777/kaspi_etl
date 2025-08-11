import { NextResponse } from 'next/server'
import { getSettings } from '@/server/db/pricebot.settings'
import { addRun } from '@/server/db/pricebot.runs'
import { RunInputSchema } from '@/server/lib/validation'
import { updatePriceBySku } from '@/server/merchant/client'

export async function POST(req: Request) {
  try {
    const t0 = Date.now()
    const raw = await req.json()
    const parsed = RunInputSchema.safeParse(raw)
    if (!parsed.success) {
      return NextResponse.json({ ok:false, code:'bad_input', message:'Invalid run input', details: parsed.error.flatten() }, { status: 400 })
    }
    const { storeId, merchantId, sku, ourPrice, opponents, dry } = parsed.data
    const mId = String(storeId || merchantId || '')
    if (!mId || !sku) return NextResponse.json({ ok:false, code:'bad_input', message:'storeId/merchantId and sku are required' }, { status:400 })
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
    const delta = (typeof ourPrice === 'number' && Number.isFinite(ourPrice)) ? (target - Number(ourPrice)) : 0

    if (dry !== false) {
      addRun({ ts: new Date().toISOString(), merchantId: mId, storeId: mId, mode: 'dry', count: 1, avgDelta: delta, applied: false })
      const ms = Date.now() - t0
      return new NextResponse(JSON.stringify({ ok:true, dry:true, sku, ourPrice, proposal:{ currentPrice: ourPrice, targetPrice: target, delta, rule: { min: item.minPrice, max: item.maxPrice, step: item.stepKzt }, opponentsUsed: opp.length, ignoredOpponents: st.globalIgnoredOpponents?.length || 0, reason: { bestOpponent: best, step: item.stepKzt, floor, ceil } } }), { headers: { 'X-Perf-ms': String(ms) } })
    }

    // Apply path (requires merchant cookie; best-effort)
    try {
      await updatePriceBySku({ sku, newPrice: target, cityId: String(process.env.DEFAULT_CITY_ID || '710000000') })
      addRun({ ts: new Date().toISOString(), merchantId: mId, storeId: mId, mode: 'apply', count: 1, avgDelta: delta, applied: true })
      const ms = Date.now() - t0
      return new NextResponse(JSON.stringify({ ok:true, dry:false, applied:true, newPrice: target, sku }), { headers: { 'X-Perf-ms': String(ms) } })
    } catch (e:any) {
      return NextResponse.json({ ok:false, code:'apply_failed', message:String(e?.message||e).slice(0,300) }, { status: 502 })
    }
  } catch (e:any) {
    return NextResponse.json({ ok:false, code:'server_error', message:String(e?.message||e) }, { status:500 })
  }
}



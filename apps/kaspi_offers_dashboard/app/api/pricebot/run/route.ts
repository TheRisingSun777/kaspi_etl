import { NextResponse } from 'next/server'
import { getSettings } from '@/server/db/pricebot.settings'
import { addRun } from '@/server/db/pricebot.runs'
import { RunInputSchema } from '@/server/lib/validation'
import { updatePriceBySku } from '@/server/merchant/client'
import { computeTargetPrice } from '@/server/pricebot/logic'

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

    // Support single or multiple skus (array). For arrays, only dry mode is supported here.
    const skus: string[] = Array.isArray(sku) ? sku.map(s=>String(s)) : [String(sku)]

    const st = getSettings(mId)

    function buildProposal(forSku: string, curPrice?: number) {
      const entry = st.sku[forSku] || { active:false, minPrice:0, maxPrice:0, stepKzt:1, intervalMin:5, ignoredOpponents:[] }
      const step = Number(entry.stepKzt || 1)
      const min = Number(entry.minPrice || 0)
      const max = Number(entry.maxPrice || 0)
      const priceNow = Number(curPrice ?? ourPrice ?? 0)
      let target = priceNow
      let reason = 'no_change'
      if (min > 0 || max > 0) {
        const out = computeTargetPrice({ ourPrice: priceNow, minPrice: min || 0, maxPrice: max || (min>0?min:priceNow), step, competitors: [] })
        target = out.target
        reason = out.reason
      }
      target = Math.max(0, Math.round(target))
      const delta = Number.isFinite(priceNow) ? target - priceNow : 0
      return { sku: forSku, ourPrice: priceNow, targetPrice: target, delta, reason, rule: { min, max, step } }
    }

    const proposals = skus.map(s => buildProposal(s, ourPrice))

    if (dry !== false) {
      const avgDelta = proposals.length ? (proposals.reduce((a,c)=>a + Number(c.delta||0), 0) / proposals.length) : 0
      addRun({ ts: new Date().toISOString(), merchantId: mId, storeId: mId, mode: 'dry', count: proposals.length, avgDelta, applied: false })
      const ms = Date.now() - t0
      const single = proposals[0]
      // Back-compat single result shape for existing UI/tests
      const legacy = {
        currentPrice: single?.ourPrice,
        targetPrice: single?.targetPrice,
        delta: single?.delta,
        rule: { min: single?.rule.min, max: single?.rule.max, step: single?.rule.step },
        opponentsUsed: 0,
        ignoredOpponents: (st.globalIgnoredOpponents?.length || 0),
        reason: single?.reason,
      }
      return new NextResponse(JSON.stringify({ ok:true, dry:true, sku, ourPrice, proposals, proposal: legacy }), { headers: { 'X-Perf-ms': String(ms) } })
    }

    // Apply path (requires merchant cookie; best-effort)
    try {
      if (skus.length !== 1) {
        return NextResponse.json({ ok:false, code:'bad_input', message:'apply supports single sku only' }, { status:400 })
      }
      const one = proposals[0]
      await updatePriceBySku({ sku: String(skus[0]), newPrice: Number(one.targetPrice||0), cityId: String(process.env.DEFAULT_CITY_ID || '710000000') })
      addRun({ ts: new Date().toISOString(), merchantId: mId, storeId: mId, mode: 'apply', count: 1, avgDelta: Number(one.delta||0), applied: true })
      const ms = Date.now() - t0
      return new NextResponse(JSON.stringify({ ok:true, dry:false, applied:true, newPrice: one.targetPrice, sku: skus[0] }), { headers: { 'X-Perf-ms': String(ms) } })
    } catch (e:any) {
      return NextResponse.json({ ok:false, code:'apply_failed', message:String(e?.message||e).slice(0,300) }, { status: 502 })
    }
  } catch (e:any) {
    return NextResponse.json({ ok:false, code:'server_error', message:String(e?.message||e) }, { status:500 })
  }
}



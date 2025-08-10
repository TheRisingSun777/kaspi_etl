import { NextResponse } from 'next/server'
import { listActiveOffers, flushMerchantDebug } from '@/server/merchant/client'
import { listRules, getRule } from '@/server/db/rules'

export async function GET() {
  try {
    const offers = await listActiveOffers()
    const rules = listRules()
    const ruleMap = new Map(rules.map(r => [r.variantId, r]))
    const rows = offers.map(o => ({
      name: o.name,
      variantProductId: o.variantProductId,
      ourPrice: o.price,
      rules: ruleMap.get(o.variantProductId) || null,
      opponentCount: 0,
    }))
    const debug = flushMerchantDebug()
    return NextResponse.json({ rows, debug })
  } catch (e:any) {
    return NextResponse.json({ error: e?.message || 'internal' }, { status: 500 })
  }
}



import { NextRequest, NextResponse } from 'next/server'
import { getRule } from '@/server/db/rules'
import { computeTargetPrice } from '@/server/pricebot/logic'
import { listActiveOffers, updatePrice } from '@/server/merchant/client'
import { scrapeAnalyze } from '@/server/scrape'

export async function POST(req: NextRequest, { params }: { params: { variantId: string } }) {
  const id = params.variantId
  const rule = getRule(id)
  if (!rule) return NextResponse.json({ error: 'no rule' }, { status: 400 })

  const offers = await listActiveOffers()
  const offer = offers.find(o => o.variantProductId === id)
  if (!offer) return NextResponse.json({ error: 'offer not found' }, { status: 404 })

  // Use our existing analyze flow to collect opponents for same city
  const cityId = process.env.DEFAULT_CITY_ID || '710000000'
  const analysis = await scrapeAnalyze(id, cityId)
  const competitors = analysis.variants[0]?.sellers?.map(s => ({ seller: s.name, price: s.price })) || []

  const { target, reason } = computeTargetPrice({
    ourPrice: offer.price,
    minPrice: rule.minPrice,
    maxPrice: rule.maxPrice,
    step: rule.step,
    competitors,
  })
  if (target !== offer.price) {
    const res = await updatePrice(id, target)
    return NextResponse.json({ ok: res.ok, status: res.status, oldPrice: offer.price, targetPrice: target, reason })
  }
  return NextResponse.json({ ok: true, status: 200, oldPrice: offer.price, targetPrice: offer.price, reason: 'no_change' })
}



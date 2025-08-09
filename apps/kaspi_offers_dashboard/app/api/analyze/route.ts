import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import type { AnalyzeResult } from '@/lib/types'
import { scrapeAnalyze } from '@/server/scrape'

const InputSchema = z.object({
  masterProductId: z.string().min(1),
  cityId: z.string().optional(),
})

export async function POST(req: NextRequest) {
  try {
    const json = await req.json()
    const input = InputSchema.parse(json)
    const cityId = input.cityId || process.env.DEFAULT_CITY_ID || '710000000'
    const result = await scrapeAnalyze(input.masterProductId, cityId)

    // Aggregate analytics (explicit formula)
    const uniqueSellers = new Set<string>()
    const spreads: number[] = []
    const spreadRatios: number[] = []
    let botCount = 0
    let sellerCount = 0
    for (const v of result.variants) {
      const prices = v.sellers.map(s=>s.price).filter(n=>Number.isFinite(n)) as number[]
      if (prices.length >= 2) {
        const min = Math.min(...prices)
        const max = Math.max(...prices)
        const spread = max - min
        spreads.push(spread)
        if (min > 0) spreadRatios.push(Math.max(0, Math.min(1, spread/min)))
      }
      for (const s of v.sellers) {
        uniqueSellers.add(s.name.trim().toLowerCase())
        sellerCount++
        if (s.isPriceBot) botCount++
      }
    }
    const avg = (arr: number[]) => arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0
    const median = (arr: number[]) => {
      if (!arr.length) return 0
      const s = [...arr].sort((a,b)=>a-b)
      const m = Math.floor(s.length/2)
      return s.length%2? s[m] : (s[m-1]+s[m])/2
    }
    const clamp01 = (x:number)=> Math.max(0, Math.min(1, x))
    const totalUniqueSellers = uniqueSellers.size
    const avgSpread = avg(spreads)
    const medianSpread = median(spreads)
    const maxSpread = spreads.length ? Math.max(...spreads) : 0
    const botShare = sellerCount ? botCount / sellerCount : 0
    const spreadRatio = avg(spreadRatios) // 0..1
    const compScore = clamp01(totalUniqueSellers/12)
    const avgRating = 0 // per-variant ratings are attached; a future step can average
    const ratingScore = clamp01(avgRating/5)
    const attractivenessIndex = Math.round(
      100 * (
        0.40 * (1 - spreadRatio) +
        0.30 * compScore +
        0.20 * ratingScore +
        0.10 * (1 - botShare)
      )
    )
    const enriched: AnalyzeResult = {
      ...result,
      uniqueSellers: totalUniqueSellers,
      analytics: { avgSpread, medianSpread, maxSpread, botShare, attractivenessIndex }
    }
    return NextResponse.json(enriched, { status: 200 })
  } catch (e: any) {
    const msg = String(e?.message || '')
    const status = /429/.test(msg) ? 429 : /timeout|503/i.test(msg) ? 503 : 400
    return NextResponse.json({ error: msg || 'Analyze failed', variants: [] }, { status })
  }
}



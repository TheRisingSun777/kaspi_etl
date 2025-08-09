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

    // Aggregate analytics
    const uniqueSellers = new Set<string>()
    const spreads: number[] = []
    let botCount = 0
    let sellerCount = 0
    for (const v of result.variants) {
      for (const s of v.sellers) {
        uniqueSellers.add(s.name)
        sellerCount++
        if (typeof s.isPriceBot === 'boolean' && s.isPriceBot) botCount++
      }
      if (typeof v.minPrice === 'number' && typeof v.maxPrice === 'number') {
        spreads.push(Math.max(0, v.maxPrice - v.minPrice))
      }
    }
    const avg = (arr: number[]) => arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0
    const median = (arr: number[]) => {
      if (!arr.length) return 0
      const s = [...arr].sort((a,b)=>a-b)
      const m = Math.floor(s.length/2)
      return s.length%2? s[m] : (s[m-1]+s[m])/2
    }
    const totalUniqueSellers = uniqueSellers.size
    const avgSpread = avg(spreads)
    const medianSpread = median(spreads)
    const maxSpread = spreads.length ? Math.max(...spreads) : 0
    const botShare = sellerCount ? Math.round((botCount/sellerCount)*100) : 0
    const avgRating = result.ratingCount ?? 0
    const attractivenessIndex = Math.max(0, Math.min(100, Math.round(100 - (avgSpread/100) - botShare + Math.min(30, totalUniqueSellers))))
    const enriched: AnalyzeResult = {
      ...result,
      analytics: { totalUniqueSellers, avgSpread, medianSpread, maxSpread, botShare, attractivenessIndex }
    }
    return NextResponse.json(enriched, { status: 200 })
  } catch (e: any) {
    const msg = String(e?.message || '')
    const status = /429/.test(msg) ? 429 : /timeout|503/i.test(msg) ? 503 : 400
    return NextResponse.json({ error: msg || 'Analyze failed', variants: [] }, { status })
  }
}



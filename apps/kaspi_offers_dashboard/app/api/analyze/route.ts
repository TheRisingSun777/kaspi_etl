import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import type { AnalyzeResult } from '@/server/scrape'
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
    const result: AnalyzeResult = await scrapeAnalyze(input.masterProductId, cityId)
    return NextResponse.json(result, { status: 200 })
  } catch (e: any) {
    const msg = String(e?.message || '')
    const status = /429/.test(msg) ? 429 : /timeout|503/i.test(msg) ? 503 : 400
    return NextResponse.json({ error: msg || 'Analyze failed', variants: [] }, { status })
  }
}



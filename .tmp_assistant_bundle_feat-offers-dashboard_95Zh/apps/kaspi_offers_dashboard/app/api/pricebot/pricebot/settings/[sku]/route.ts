import { NextResponse } from 'next/server'
import { upsertSettings } from '@/lib/pricebot/storage'

export async function PATCH(request: Request, { params }: { params: { sku: string } }) {
  const body = await request.json()
  const sku = decodeURIComponent(params.sku)
  const updated = upsertSettings(sku, body)
  return NextResponse.json({ ok: true, sku, settings: updated })
}



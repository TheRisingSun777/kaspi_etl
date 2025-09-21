import { NextResponse } from 'next/server'
import { toggleIgnore } from '@/lib/pricebot/storage'

export async function POST(request: Request) {
  const { sku, seller, ignore } = await request.json()
  const updated = toggleIgnore(String(sku), String(seller), !!ignore)
  return NextResponse.json({ ok: true, sku, settings: updated })
}



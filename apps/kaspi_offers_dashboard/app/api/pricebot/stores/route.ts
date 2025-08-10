import { NextResponse } from 'next/server'

export function GET() {
  const raw = process.env.KASPI_STORE_IDS || process.env.KASPI_MERCHANT_ID || ''
  const ids = raw.split(',').map(s=>s.trim()).filter(Boolean)
  const items = ids.map((id, idx)=>({ id, name: `Store ${idx+1}` }))
  return NextResponse.json({ ok:true, items })
}



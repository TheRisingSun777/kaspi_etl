import { NextRequest, NextResponse } from 'next/server'
import { setIgnoreSeller } from '@/server/db/rules'

export async function PUT(req: NextRequest, { params }: { params: { variantId: string } }) {
  const id = params.variantId
  const json = await req.json().catch(()=>null) as any
  const sellerName = String(json?.sellerName||'').trim()
  const ignore = Boolean(json?.ignore)
  if (!sellerName) return NextResponse.json({ error: 'sellerName required' }, { status: 400 })
  setIgnoreSeller(id, sellerName, ignore)
  return NextResponse.json({ ok: true })
}



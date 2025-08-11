import { NextResponse } from 'next/server'
import { readMerchants, writeMerchants } from '@/server/merchants'

export function GET() {
  const items = readMerchants().map(m=>({ id: m.merchantId, name: m.label, cityId: m.cityId }))
  return NextResponse.json({ ok:true, items })
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const list = readMerchants()
    const idx = list.findIndex(m=>m.merchantId===body.merchantId)
    const next = { merchantId: String(body.merchantId), label: String(body.label||body.merchantId), cityId: Number(body.cityId||710000000), cookieFile: body.cookieFile, apiKey: body.apiKey }
    if (idx>=0) list[idx] = next; else list.push(next)
    writeMerchants(list)
    return NextResponse.json({ ok:true, items:list })
  } catch (e:any) {
    return NextResponse.json({ ok:false, error:String(e?.message||e) }, { status:400 })
  }
}



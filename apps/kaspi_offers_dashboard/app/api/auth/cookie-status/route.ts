import { NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'

function statIfExists(p: string) {
  try { const st = fs.statSync(p); return st } catch { return null }
}

export async function POST(req: Request) {
  try {
    const { merchantId } = await req.json().catch(()=>({})) as any
    const m = String(merchantId||'').trim()
    if (!m) return NextResponse.json({ ok:false, code:'bad_input', message:'merchantId required' }, { status:400 })
    const candidates = [
      path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'cookies', `${m}.json`),
      path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'db', 'merchants', `${m}.cookie.json`),
      path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'merchant', `${m}.cookie.json`),
    ]
    for (const p of candidates) {
      const st = statIfExists(p)
      if (st) {
        const ageSeconds = Math.floor((Date.now() - st.mtimeMs) / 1000)
        return NextResponse.json({ ok:true, exists:true, path: p, ageSeconds })
      }
    }
    return NextResponse.json({ ok:true, exists:false })
  } catch (e:any) {
    return NextResponse.json({ ok:false, code:'server_error', message:String(e?.message||e) }, { status:500 })
  }
}



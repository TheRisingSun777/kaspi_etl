import { NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'

const STATE_FILE = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'docs', 'STATE.json')

export async function GET() {
  try {
    const raw = fs.readFileSync(STATE_FILE, 'utf-8')
    const js = JSON.parse(raw)
    return NextResponse.json({ ok: true, state: js })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(()=>({})) as any
    const storeId = body?.storeId
    const merchantId = body?.merchantId
    const cityId = body?.cityId
    let cur: any = {}
    try { cur = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8')) } catch {}
    const next = {
      ...cur,
      storeId: typeof storeId !== 'undefined' ? storeId : (cur?.storeId ?? null),
      merchantId: typeof merchantId !== 'undefined' ? merchantId : (cur?.merchantId ?? null),
      cityId: typeof cityId !== 'undefined' ? cityId : (cur?.cityId ?? null),
      lastSeen: { ...(cur?.lastSeen||{}), taskId: (cur?.lastSeen?.taskId||'UI-002') },
    }
    const tmp = STATE_FILE + '.tmp'
    fs.writeFileSync(tmp, JSON.stringify(next, null, 2))
    fs.renameSync(tmp, STATE_FILE)
    return NextResponse.json({ ok: true, state: next })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}



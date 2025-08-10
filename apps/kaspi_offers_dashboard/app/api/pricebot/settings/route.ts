import { NextResponse } from 'next/server'
import { getSettings, upsertPerSku, updateGlobalIgnore } from '@/server/db/pricebot.store'

export async function GET() {
  const st = getSettings()
  return NextResponse.json({ ok: true, settings: st })
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    if (Array.isArray(body?.globalIgnoreSellers)) {
      const list = updateGlobalIgnore(body.globalIgnoreSellers.map(String))
      return NextResponse.json({ ok: true, settings: { globalIgnoreSellers: list } })
    }
    const sku = String(body?.sku || '')
    const updates = body?.updates || {}
    if (!sku) return NextResponse.json({ ok: false, error: 'MISSING_SKU' }, { status: 400 })
    const next = upsertPerSku(sku, {
      active: toBool(updates.active),
      min: toNum(updates.min),
      max: toNum(updates.max),
      step: toNum(updates.step),
      intervalMinutes: toNum(updates.intervalMinutes),
      ignoreSellers: Array.isArray(updates.ignoreSellers) ? updates.ignoreSellers.map(String) : undefined,
    })
    return NextResponse.json({ ok: true, sku, settings: next })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}

function toNum(v: any): number | undefined { const n = Number(v); return Number.isFinite(n) ? n : undefined }
function toBool(v: any): boolean | undefined {
  if (typeof v === 'boolean') return v
  if (typeof v === 'string') return /^(1|true|on|yes)$/i.test(v)
  if (typeof v === 'number') return v !== 0
  return undefined
}

import { NextRequest, NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'

const SETTINGS_DIR = path.join(process.cwd(), 'server', 'db')
const SETTINGS_PATH = path.join(SETTINGS_DIR, 'pricebot.settings.json')

function readSettings() {
  try {
    if (!fs.existsSync(SETTINGS_PATH)) return {}
    return JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf8'))
  } catch { return {} }
}
function writeSettings(partial: any) {
  const cur = readSettings()
  const next = { ...cur, ...partial }
  if (!fs.existsSync(SETTINGS_DIR)) fs.mkdirSync(SETTINGS_DIR, { recursive: true })
  fs.writeFileSync(SETTINGS_PATH, JSON.stringify(next, null, 2), 'utf8')
  return next
}

export async function GET() {
  const s = readSettings()
  return NextResponse.json({ settings: s })
}

export async function PUT(req: NextRequest) {
  const json = await req.json().catch(()=>null)
  if (!json) return NextResponse.json({ error: 'invalid body' }, { status: 400 })
  const s = writeSettings({
    base: typeof json.base === 'string' ? json.base : undefined,
    merchantId: typeof json.merchantId === 'string' ? json.merchantId : undefined,
  })
  return NextResponse.json({ settings: s })
}



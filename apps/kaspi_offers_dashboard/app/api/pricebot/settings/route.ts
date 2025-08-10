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



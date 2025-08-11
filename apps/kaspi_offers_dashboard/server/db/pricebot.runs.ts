import fs from 'node:fs'
import path from 'node:path'

export type RunRecord = {
  ts: string
  merchantId: string
  mode: 'dry' | 'apply' | string
  count: number
  avgDelta: number
}

type FileShape = Record<string, RunRecord[]> // keyed by merchantId

const FILE = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'db', 'pricebot.runs.json')

function ensureDir() {
  const dir = path.dirname(FILE)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
}

function readAll(): FileShape {
  try {
    const raw = fs.readFileSync(FILE, 'utf-8')
    const js = JSON.parse(raw)
    if (js && typeof js === 'object' && !Array.isArray(js)) return js as FileShape
  } catch {}
  return {}
}

function writeAll(all: FileShape) {
  ensureDir()
  const tmp = FILE + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify(all, null, 2))
  fs.renameSync(tmp, FILE)
}

export function addRun(rec: RunRecord) {
  const all = readAll()
  const k = String(rec.merchantId)
  const list = Array.isArray(all[k]) ? all[k] : []
  list.push(rec)
  // keep last 100
  all[k] = list.slice(-100)
  writeAll(all)
  return rec
}

export function getLastRun(merchantId: string): RunRecord | null {
  const all = readAll()
  const list = Array.isArray(all[merchantId]) ? all[merchantId] : []
  return list.length ? list[list.length - 1] : null
}



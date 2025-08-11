import fs from 'node:fs'
import path from 'node:path'

export type SkuSettings = {
  active: boolean
  minPrice?: number
  maxPrice?: number
  stepKzt?: number
  intervalMin?: number
  ignoredOpponents?: string[]
}

export type GlobalSettings = {
  merchantId: string
  defaultCityId: number
  globalIgnoredOpponents: string[]
  sku: Record<string, SkuSettings>
}

type FileShape = Record<string, GlobalSettings>

const FILE = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'db', 'pricebot.settings.json')

function ensureDir() { const dir = path.dirname(FILE); if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true }) }

function readAll(): FileShape {
  try {
    const raw = fs.readFileSync(FILE, 'utf-8')
    const js = JSON.parse(raw)
    return js && typeof js === 'object' ? js as FileShape : {}
  } catch { return {} }
}

function writeAll(all: FileShape) {
  ensureDir()
  const tmp = FILE + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify(all, null, 2))
  fs.renameSync(tmp, FILE)
}

export function getSettings(merchantId: string): GlobalSettings {
  const all = readAll()
  let cur = all[merchantId]
  if (!cur) {
    cur = { merchantId, defaultCityId: Number(process.env.DEFAULT_CITY_ID || 710000000), globalIgnoredOpponents: [], sku: {} }
    all[merchantId] = cur
    writeAll(all)
  }
  return cur
}

export function upsertSettings(merchantId: string, updates: Record<string, Partial<SkuSettings>>, globalIgnored?: string[]) {
  const all = readAll()
  const cur = all[merchantId] || { merchantId, defaultCityId: Number(process.env.DEFAULT_CITY_ID || 710000000), globalIgnoredOpponents: [], sku: {} }
  const sku = { ...cur.sku }
  for (const [k, v] of Object.entries(updates || {})) {
    const base: SkuSettings = sku[k] || { active: false }
    sku[k] = {
      active: typeof v.active === 'boolean' ? v.active : base.active,
      minPrice: numOr(base.minPrice, v.minPrice),
      maxPrice: numOr(base.maxPrice, v.maxPrice),
      stepKzt: numOr(base.stepKzt, v.stepKzt),
      intervalMin: numOr(base.intervalMin, v.intervalMin),
      ignoredOpponents: Array.isArray(v.ignoredOpponents) ? uniq(v.ignoredOpponents) : base.ignoredOpponents,
    }
  }
  const next: GlobalSettings = {
    ...cur,
    globalIgnoredOpponents: Array.isArray(globalIgnored) ? uniq(globalIgnored) : cur.globalIgnoredOpponents,
    sku,
  }
  all[merchantId] = next
  writeAll(all)
  return next
}

function uniq(arr: string[] = []) { return Array.from(new Set(arr.map(String).map(s=>s.trim()).filter(Boolean))) }
function numOr(a?: number, b?: number) { const n = Number(b); return Number.isFinite(n) ? n : a }



import fs from 'node:fs'
import path from 'node:path'

export type SkuSettings = { active: boolean; min: number; max: number; step: number; intervalMin: number; ignore: string[] }
export type StoreShard = { globalIgnore: string[]; bySku: Record<string, SkuSettings> }

const FILE = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'db', 'pricebot.json')

function ensureDir() { const dir = path.dirname(FILE); if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true }) }

function readAll(): Record<string, StoreShard> {
  try {
    const raw = fs.readFileSync(FILE, 'utf-8')
    const json = JSON.parse(raw)
    if (json && typeof json === 'object' && !Array.isArray(json)) {
      // detect legacy shape and migrate on the fly
      if (json.global || json.items) {
        const legacy: any = json
        const bySku: Record<string, SkuSettings> = {}
        for (const [sku, it] of Object.entries<any>(legacy.items || {})) {
          bySku[sku] = {
            active: !!it.active,
            min: Number(it.min || 0),
            max: Number(it.max || 0),
            step: Number(it.step || 1),
            intervalMin: Number(it.interval || 5),
            ignore: Array.isArray(it.ignoreSellers) ? it.ignoreSellers : [],
          }
        }
        const shard: StoreShard = { globalIgnore: legacy.global?.ignoreSellers || [], bySku }
        const storeId = process.env.KASPI_MERCHANT_ID || 'default'
        return { [storeId]: shard }
      }
      return json as Record<string, StoreShard>
    }
  } catch {}
  return {}
}

function writeAll(all: Record<string, StoreShard>) {
  ensureDir()
  const tmp = FILE + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify(all, null, 2))
  fs.renameSync(tmp, FILE)
}

export function getStore(storeId: string): StoreShard {
  const all = readAll()
  const shard = all[storeId]
  if (shard) return shard
  return { globalIgnore: [], bySku: {} }
}

export function setStore(storeId: string, shard: StoreShard) {
  const all = readAll()
  all[storeId] = shard
  writeAll(all)
}

export function upsertSettings(storeId: string, batch: Record<string, Partial<SkuSettings>>) {
  const cur = getStore(storeId)
  const next: StoreShard = { ...cur, bySku: { ...cur.bySku } }
  for (const [sku, patch] of Object.entries(batch)) {
    const base: SkuSettings = next.bySku[sku] || { active: false, min: 0, max: 0, step: 1, intervalMin: 5, ignore: [] }
    next.bySku[sku] = {
      active: patch.active ?? base.active,
      min: isNum(patch.min) ? Number(patch.min) : base.min,
      max: isNum(patch.max) ? Number(patch.max) : base.max,
      step: isNum(patch.step) ? Number(patch.step) : base.step,
      intervalMin: isNum(patch.intervalMin) ? Number(patch.intervalMin) : base.intervalMin,
      ignore: Array.isArray(patch.ignore) ? uniq(patch.ignore) : base.ignore,
    }
  }
  setStore(storeId, next)
  return next
}

export function toggleIgnore(storeId: string, sku: string, sellerId: string, ignore: boolean) {
  const cur = getStore(storeId)
  const base: SkuSettings = cur.bySku[sku] || { active: false, min: 0, max: 0, step: 1, intervalMin: 5, ignore: [] }
  const set = new Set(base.ignore)
  if (ignore) set.add(sellerId); else set.delete(sellerId)
  cur.bySku[sku] = { ...base, ignore: Array.from(set) }
  setStore(storeId, cur)
  return cur.bySku[sku]
}

export function setGlobalIgnore(storeId: string, sellers: string[]) {
  const cur = getStore(storeId)
  cur.globalIgnore = uniq(sellers)
  setStore(storeId, cur)
  return cur
}

export function mergedIgnoredForSku(storeId: string, sku: string): string[] {
  const cur = getStore(storeId)
  return uniq([...(cur.globalIgnore||[]), ...((cur.bySku[sku]?.ignore)||[])])
}

function uniq(arr: string[]): string[] { return Array.from(new Set((arr||[]).map(String).map(s=>s.trim()).filter(Boolean))) }
function isNum(v:any){ const n = Number(v); return Number.isFinite(n) }



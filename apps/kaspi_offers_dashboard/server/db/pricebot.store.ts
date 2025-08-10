import fs from 'node:fs'
import path from 'node:path'

export type PerSku = {
  active: boolean
  min: number
  max: number
  step: number
  intervalMinutes: number
  ignoreSellers: string[]
}

export type PricebotStore = {
  globalIgnoreSellers: string[]
  perSku: Record<string, PerSku>
}

const FILE = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'db', 'pricebot.json')

function ensureDir() {
  const dir = path.dirname(FILE)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
}

export function readStore(): PricebotStore {
  try {
    const raw = fs.readFileSync(FILE, 'utf-8')
    const json = JSON.parse(raw)
    return {
      globalIgnoreSellers: Array.isArray(json.globalIgnoreSellers) ? json.globalIgnoreSellers : [],
      perSku: typeof json.perSku === 'object' && json.perSku ? json.perSku : {},
    }
  } catch {
    return { globalIgnoreSellers: [], perSku: {} }
  }
}

export function writeStore(next: PricebotStore) {
  ensureDir()
  const tmp = FILE + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify(next, null, 2))
  fs.renameSync(tmp, FILE)
}

export function upsertPerSku(sku: string, patch: Partial<PerSku>): PerSku {
  const cur = readStore()
  const base: PerSku = cur.perSku[sku] || { active: false, min: 0, max: 0, step: 1, intervalMinutes: 5, ignoreSellers: [] }
  const next: PerSku = {
    active: patch.active ?? base.active,
    min: isFiniteNumber(patch.min) ? Number(patch.min) : base.min,
    max: isFiniteNumber(patch.max) ? Number(patch.max) : base.max,
    step: isFiniteNumber(patch.step) ? Number(patch.step) : base.step,
    intervalMinutes: clampInterval(patch.intervalMinutes ?? base.intervalMinutes),
    ignoreSellers: Array.isArray(patch.ignoreSellers) ? uniqueStrings(patch.ignoreSellers) : base.ignoreSellers,
  }
  const merged: PricebotStore = { ...cur, perSku: { ...cur.perSku, [sku]: next } }
  writeStore(merged)
  return next
}

export function updateGlobalIgnore(list: string[]): string[] {
  const cur = readStore()
  const next: PricebotStore = { ...cur, globalIgnoreSellers: uniqueStrings(list) }
  writeStore(next)
  return next.globalIgnoreSellers
}

export function getSettings(sku?: string) {
  const st = readStore()
  if (sku) return st.perSku[sku] || { active: false, min: 0, max: 0, step: 1, intervalMinutes: 5, ignoreSellers: [] }
  return st
}

function isFiniteNumber(v: any): v is number { return typeof v === 'number' && Number.isFinite(v) }
function clampInterval(v: number) { const n = Math.max(1, Math.min(15, Number(v || 5))); return n }
function uniqueStrings(arr: string[]): string[] { return Array.from(new Set((arr||[]).map(String).map(s=>s.trim()).filter(Boolean))) }



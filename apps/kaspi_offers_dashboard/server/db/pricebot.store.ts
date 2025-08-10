import fs from 'node:fs'
import path from 'node:path'

export type ItemSettings = {
  active: boolean
  min: number
  max: number
  step: number
  interval: number
  ignoreSellers: string[]
}

export type PricebotStore = {
  global: { cityId: string; ignoreSellers: string[] }
  items: Record<string, ItemSettings>
  updatedAt: string
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
    const global = json.global || { cityId: process.env.DEFAULT_CITY_ID || '710000000', ignoreSellers: [] }
    const items = json.items || {}
    const updatedAt = json.updatedAt || new Date().toISOString()
    return { global, items, updatedAt }
  } catch {
    return { global: { cityId: String(process.env.DEFAULT_CITY_ID || '710000000'), ignoreSellers: [] }, items: {}, updatedAt: new Date().toISOString() }
  }
}

export function writeStore(next: PricebotStore) {
  ensureDir()
  const tmp = FILE + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify(next, null, 2))
  fs.renameSync(tmp, FILE)
}

export function upsertItemsBatch(batch: Record<string, Partial<ItemSettings>>) {
  const cur = readStore()
  const nextItems: Record<string, ItemSettings> = { ...cur.items }
  for (const [sku, patch] of Object.entries(batch)) {
    const base: ItemSettings = nextItems[sku] || { active: false, min: 0, max: 0, step: 1, interval: 5, ignoreSellers: [] }
    nextItems[sku] = {
      active: patch.active ?? base.active,
      min: pickNum(patch.min, base.min),
      max: pickNum(patch.max, base.max),
      step: pickNum(patch.step, base.step),
      interval: clampInterval(patch.interval ?? base.interval),
      ignoreSellers: Array.isArray(patch.ignoreSellers) ? uniq(patch.ignoreSellers) : base.ignoreSellers,
    }
  }
  const next: PricebotStore = { ...cur, items: nextItems, updatedAt: new Date().toISOString() }
  writeStore(next)
  return next
}

export function updateGlobal(patch: Partial<{ cityId: string; ignoreSellers: string[] }>) {
  const cur = readStore()
  const next: PricebotStore = {
    ...cur,
    global: {
      cityId: String(patch.cityId || cur.global.cityId || process.env.DEFAULT_CITY_ID || '710000000'),
      ignoreSellers: Array.isArray(patch.ignoreSellers) ? uniq(patch.ignoreSellers) : cur.global.ignoreSellers,
    },
    updatedAt: new Date().toISOString(),
  }
  writeStore(next)
  return next
}

export function getItemSettingsOrDefault(sku: string): ItemSettings {
  const st = readStore()
  return st.items[sku] || { active: false, min: 0, max: 0, step: 1, interval: 5, ignoreSellers: [] }
}

function pickNum(v: any, fallback: number) { const n = Number(v); return Number.isFinite(n) ? n : fallback }
function clampInterval(v: number) { const n = Math.max(1, Math.min(15, Number(v || 5))); return n }
function uniq(arr: string[]): string[] { return Array.from(new Set((arr||[]).map(String).map(s=>s.trim()).filter(Boolean))) }



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

export type PricebotProfile = { id: string; name: string; cityId: string }

export type PricebotStore = {
  global: { cityId: string; ignoreSellers: string[] }
  profiles?: PricebotProfile[]
  activeProfileId?: string
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
    const profiles = Array.isArray(json.profiles) ? json.profiles : defaultProfiles(global.cityId)
    const activeProfileId = typeof json.activeProfileId === 'string' ? json.activeProfileId : profiles?.[0]?.id
    const updatedAt = json.updatedAt || new Date().toISOString()
    return { global, profiles, activeProfileId, items, updatedAt }
  } catch {
    const global = { cityId: String(process.env.DEFAULT_CITY_ID || '710000000'), ignoreSellers: [] }
    return { global, profiles: defaultProfiles(global.cityId), activeProfileId: 'store-1', items: {}, updatedAt: new Date().toISOString() }
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

export function upsertItemIgnoreSeller(sku: string, merchantId: string, ignore: boolean) {
  const cur = readStore()
  const base: ItemSettings = cur.items[sku] || { active: false, min: 0, max: 0, step: 1, interval: 5, ignoreSellers: [] }
  const set = new Set(base.ignoreSellers)
  if (ignore) set.add(merchantId); else set.delete(merchantId)
  const next: PricebotStore = { ...cur, items: { ...cur.items, [sku]: { ...base, ignoreSellers: Array.from(set) } }, updatedAt: new Date().toISOString() }
  writeStore(next)
  return next.items[sku]
}

export function getMergedIgnoreForSku(sku: string): string[] {
  const st = readStore()
  const item = st.items[sku]
  const set = new Set([ ...(st.global.ignoreSellers || []), ...((item?.ignoreSellers) || []) ])
  return Array.from(set)
}

export function getActiveCityId(): string {
  const st = readStore()
  const id = st.activeProfileId
  const p = (st.profiles || []).find(x=>x.id===id)
  return p?.cityId || st.global.cityId
}

function defaultProfiles(cityId: string): PricebotProfile[] {
  return [1,2,3,4,5].map(i=>({ id: `store-${i}`, name: `Store ${i}`, cityId }))
}

function pickNum(v: any, fallback: number) { const n = Number(v); return Number.isFinite(n) ? n : fallback }
function clampInterval(v: number) { const n = Math.max(1, Math.min(15, Number(v || 5))); return n }
function uniq(arr: string[]): string[] { return Array.from(new Set((arr||[]).map(String).map(s=>s.trim()).filter(Boolean))) }



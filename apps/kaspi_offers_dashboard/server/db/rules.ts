import Database from 'better-sqlite3'
import path from 'node:path'
import fs from 'node:fs'

const DB_DIR = path.join(process.cwd(), 'server', 'db')
const DB_PATH = path.join(DB_DIR, 'pricing.sqlite')

if (!fs.existsSync(DB_DIR)) fs.mkdirSync(DB_DIR, { recursive: true })
const db = new Database(DB_PATH)

// Create tables
db.exec(`
CREATE TABLE IF NOT EXISTS pricing_rules (
  variant_id TEXT PRIMARY KEY,
  min_price INTEGER NOT NULL,
  max_price INTEGER NOT NULL,
  step INTEGER NOT NULL DEFAULT 1,
  interval_min INTEGER NOT NULL DEFAULT 5,
  active INTEGER NOT NULL DEFAULT 1,
  updated_at DATETIME
);
CREATE TABLE IF NOT EXISTS ignored_sellers (
  variant_id TEXT NOT NULL,
  seller_name TEXT NOT NULL,
  PRIMARY KEY (variant_id, seller_name)
);
`)

export type PricingRule = {
  variantId: string
  minPrice: number
  maxPrice: number
  step: number
  intervalMin: number
  active: number
}

export function upsertRule(rule: PricingRule) {
  const stmt = db.prepare(`REPLACE INTO pricing_rules(variant_id,min_price,max_price,step,interval_min,active,updated_at)
    VALUES(@variantId,@minPrice,@maxPrice,@step,@intervalMin,@active,datetime('now'))`)
  stmt.run(rule as any)
}

export function getRule(variantId: string): PricingRule | null {
  const row = db.prepare(`SELECT variant_id as variantId, min_price as minPrice, max_price as maxPrice, step, interval_min as intervalMin, active FROM pricing_rules WHERE variant_id=?`).get(variantId)
  return row || null
}

export function listRules(): PricingRule[] {
  return db.prepare(`SELECT variant_id as variantId, min_price as minPrice, max_price as maxPrice, step, interval_min as intervalMin, active FROM pricing_rules`).all()
}

export function setIgnoreSeller(variantId: string, sellerName: string, ignore: boolean) {
  if (ignore) db.prepare(`REPLACE INTO ignored_sellers(variant_id, seller_name) VALUES(?,?)`).run(variantId, sellerName)
  else db.prepare(`DELETE FROM ignored_sellers WHERE variant_id=? AND seller_name=?`).run(variantId, sellerName)
}

export function listIgnored(variantId: string): string[] {
  const rows = db.prepare(`SELECT seller_name FROM ignored_sellers WHERE variant_id=?`).all(variantId)
  return rows.map((r:any)=> String(r.seller_name))
}



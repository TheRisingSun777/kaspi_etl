import path from 'node:path'
import fs from 'node:fs'

const DB_DIR = path.join(process.cwd(), 'server', 'db')
const DB_PATH = path.join(DB_DIR, 'pricing.sqlite')
const JSON_PATH = path.join(DB_DIR, 'pricing.rules.json')

if (!fs.existsSync(DB_DIR)) fs.mkdirSync(DB_DIR, { recursive: true })

let db: any = null
let mode: 'sqlite' | 'json' = 'json'
try {
  // Using require here to avoid bundling native module in edge runtimes
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const Database = require('better-sqlite3')
  db = new Database(DB_PATH)
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
  mode = 'sqlite'
} catch {
  mode = 'json'
  if (!fs.existsSync(JSON_PATH)) fs.writeFileSync(JSON_PATH, JSON.stringify({ rules: {}, ignored: {} }, null, 2), 'utf8')
}

export type PricingRule = {
  variantId: string
  minPrice: number
  maxPrice: number
  step: number
  intervalMin: number
  active: number
}

export function upsertRule(rule: PricingRule) {
  if (mode === 'sqlite') {
    const stmt = db.prepare(`REPLACE INTO pricing_rules(variant_id,min_price,max_price,step,interval_min,active,updated_at)
      VALUES(@variantId,@minPrice,@maxPrice,@step,@intervalMin,@active,datetime('now'))`)
    stmt.run(rule as any)
  } else {
    const doc = JSON.parse(fs.readFileSync(JSON_PATH, 'utf8'))
    doc.rules[rule.variantId] = { ...rule }
    fs.writeFileSync(JSON_PATH, JSON.stringify(doc, null, 2), 'utf8')
  }
}

export function getRule(variantId: string): PricingRule | null {
  if (mode === 'sqlite') {
    const row = db.prepare(`SELECT variant_id as variantId, min_price as minPrice, max_price as maxPrice, step, interval_min as intervalMin, active FROM pricing_rules WHERE variant_id=?`).get(variantId)
    return row || null
  } else {
    const doc = JSON.parse(fs.readFileSync(JSON_PATH, 'utf8'))
    return doc.rules[variantId] || null
  }
}

export function listRules(): PricingRule[] {
  if (mode === 'sqlite') {
    return db.prepare(`SELECT variant_id as variantId, min_price as minPrice, max_price as maxPrice, step, interval_min as intervalMin, active FROM pricing_rules`).all()
  } else {
    const doc = JSON.parse(fs.readFileSync(JSON_PATH, 'utf8'))
    return Object.values(doc.rules)
  }
}

export function setIgnoreSeller(variantId: string, sellerName: string, ignore: boolean) {
  if (mode === 'sqlite') {
    if (ignore) db.prepare(`REPLACE INTO ignored_sellers(variant_id, seller_name) VALUES(?,?)`).run(variantId, sellerName)
    else db.prepare(`DELETE FROM ignored_sellers WHERE variant_id=? AND seller_name=?`).run(variantId, sellerName)
  } else {
    const doc = JSON.parse(fs.readFileSync(JSON_PATH, 'utf8'))
    doc.ignored[variantId] = doc.ignored[variantId] || {}
    if (ignore) doc.ignored[variantId][sellerName] = true
    else delete doc.ignored[variantId][sellerName]
    fs.writeFileSync(JSON_PATH, JSON.stringify(doc, null, 2), 'utf8')
  }
}

export function listIgnored(variantId: string): string[] {
  if (mode === 'sqlite') {
    const rows = db.prepare(`SELECT seller_name FROM ignored_sellers WHERE variant_id=?`).all(variantId)
    return rows.map((r:any)=> String(r.seller_name))
  } else {
    const doc = JSON.parse(fs.readFileSync(JSON_PATH, 'utf8'))
    return Object.keys(doc.ignored[variantId] || {})
  }
}



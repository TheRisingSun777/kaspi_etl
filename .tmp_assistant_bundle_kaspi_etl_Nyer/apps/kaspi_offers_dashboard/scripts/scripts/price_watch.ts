#!/usr/bin/env tsx
/*
  Price Watch (CORE-LOOP-004): periodically reads settings and calls /api/pricebot/run?dry=true
  for SKUs that are due by interval, logging proposals.

  Args/env:
    --merchantId, --storeId, env KASPI_MERCHANT_ID|STORE_ID|KASPI_STORE_ID
    --city, env DEFAULT_CITY_ID|KASPI_CITY_ID (default 710000000)
    --pollSec, env PRICE_WATCH_POLL_SEC|WATCH_INTERVAL_SEC (default 60)
    env PRICEBOT_API_BASE (default http://localhost:3001)
*/
import fs from 'node:fs'
import path from 'node:path'
import { getSettings } from '@/server/db/pricebot.settings'

type Args = { merchantId: string; city: string; pollSec: number }

function parseArgs(): Args {
  const arg = Object.fromEntries(process.argv.slice(2).map((x) => {
    const [k, v] = x.split('=')
    return [k.replace(/^--/, ''), v]
  })) as any
  const merchantId = String(
    arg.merchantId ||
    arg.storeId ||
    process.env.KASPI_MERCHANT_ID ||
    process.env.STORE_ID ||
    process.env.KASPI_STORE_ID ||
    ''
  )
  const city = String(arg.city || process.env.DEFAULT_CITY_ID || process.env.KASPI_CITY_ID || '710000000')
  const pollSec = Number(arg.pollSec || process.env.PRICE_WATCH_POLL_SEC || process.env.WATCH_INTERVAL_SEC || 60)
  return { merchantId, city, pollSec }
}

function ndjsonAppend(file: string, obj: unknown) {
  const dir = path.dirname(file)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  fs.appendFileSync(file, JSON.stringify(obj) + '\n')
}

// helper reserved for future stats output (unused)
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _median = (_nums: number[]): number => 0

function isDue(lastTs: number|undefined, intervalMin: number, nowMs: number): boolean {
  if (!intervalMin || intervalMin <= 0) return false
  if (!lastTs) return true
  return (nowMs - lastTs) >= intervalMin * 60_000
}

const lastRunAt: Map<string, number> = new Map()

async function tick(merchantId: string, city: string) {
  const now = Date.now()
  const st = getSettings(merchantId)
  const dueSkus: string[] = []
  for (const [sku, cfg] of Object.entries(st.sku)) {
    if (!cfg?.active) continue
    const key = `${merchantId}:${sku}`
    const lastRunTs = lastRunAt.get(key)
    const interval = Number(cfg.intervalMin || 0)
    if (isDue(lastRunTs, interval, now)) dueSkus.push(sku)
  }
  if (!dueSkus.length) {
    console.log(`[watch] no due SKUs for merchant=${merchantId}`)
    return
  }
  const apiBase = String(process.env.PRICEBOT_API_BASE || 'http://localhost:3001')
  for (const sku of dueSkus) {
    try {
      const res = await fetch(`${apiBase}/api/pricebot/run`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ storeId: merchantId, cityId: city, sku, dry: true }) })
      const js: any = await res.json().catch(()=>null)
      const p = js?.proposal || js?.proposals?.[0] || null
      if (p) {
        console.log(`[run][${merchantId}] ${sku}: our=${p.currentPrice ?? p.ourPrice} → target=${p.targetPrice} (${p.reason})`)
        lastRunAt.set(`${merchantId}:${sku}`, Date.now())
      } else {
        console.log(`[run][${merchantId}] ${sku}: no proposal`)
      }
    } catch (e:any) {
      console.error(`[run][${merchantId}] ${sku}:`, e?.message||e)
    }
  }
}

async function main() {
  const { merchantId, city, pollSec } = parseArgs()
  if (!merchantId) { console.error('Usage: tsx apps/kaspi_offers_dashboard/scripts/price_watch.ts --merchantId=30141222 --city=710000000 --pollSec=60'); process.exit(1) }
  console.log(`Price Watch: merchantId=${merchantId} city=${city} pollSec=${pollSec}`)
  // eslint-disable-next-line no-constant-condition
  while (true) {
    await tick(merchantId, city)
    await new Promise(r=>setTimeout(r, pollSec*1000))
  }
}

main()



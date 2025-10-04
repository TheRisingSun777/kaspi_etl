#!/usr/bin/env tsx
/*
  Price Watch: periodically scrapes product IDs and appends NDJSON records under data_raw/watch/<id>.ndjson
*/
import fs from 'node:fs'
import path from 'node:path'
import { scrapeAnalyze } from '@/server/scrape'

type Args = { ids: string[]; city: string; intervalSec: number }

function parseArgs(): Args {
  const arg = Object.fromEntries(process.argv.slice(2).map((x) => {
    const [k, v] = x.split('=')
    return [k.replace(/^--/, ''), v]
  })) as any
  const ids = String(arg.ids || '').split(',').map((s) => s.trim()).filter(Boolean)
  const city = String(arg.city || process.env.DEFAULT_CITY_ID || '710000000')
  const intervalSec = Number(arg.intervalSec || 60)
  return { ids, city, intervalSec }
}

function ndjsonAppend(file: string, obj: unknown) {
  const dir = path.dirname(file)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  fs.appendFileSync(file, JSON.stringify(obj) + '\n')
}

function median(nums: number[]): number { const s=[...nums].sort((a,b)=>a-b); const m=Math.floor(s.length/2); return s.length? (s.length%2? s[m] : (s[m-1]+s[m])/2) : 0 }

// sliding window of bot signals per (variantId,seller)
const botWindow: Map<string, Map<string, number[]>> = new Map()

async function tick(ids: string[], city: string) {
  const ts = new Date().toISOString()
  for (const id of ids) {
    try {
      const data = await scrapeAnalyze(id, city)
      const outFile = path.join(process.cwd(), 'data_raw', 'watch', `${id}.ndjson`)
      for (const v of data.variants) {
        const min = v.stats?.min ?? Math.min(...v.sellers.map(s=>s.price))
        const key = v.productId
        if (!botWindow.has(key)) botWindow.set(key, new Map())
        const sellersWindow = botWindow.get(key)!
        // emit one NDJSON per seller
        for (const s of v.sellers) {
          const undercut = Number.isFinite(min) ? (s.price <= (Number(min) + 50)) : false
          const sw = sellersWindow.get(s.name) || []
          sw.push(undercut ? 1 : 0)
          while (sw.length > 5) sw.shift()
          sellersWindow.set(s.name, sw)
          const repeatedUndercut = sw.reduce((a,b)=>a+b,0) >= 3
          const isPriceBot = s.isPriceBot || repeatedUndercut
          ndjsonAppend(outFile, {
            ts,
            masterProductId: id,
            variantId: v.productId,
            variantColor: v.variantColor,
            variantSize: v.variantSize || v.label,
            seller: s.name,
            price: s.price,
            deliveryDate: s.deliveryDate,
            isPriceBot,
            reviewDateOldest: v.reviewDateOldest || null,
            reviewDateLatest: v.reviewDateLatest || null,
          })
        }
      }
      const top = data.variants.flatMap(v=>v.sellers).sort((a,b)=>a.price-b.price).slice(0,3)
      const suspected = data.variants.flatMap(v=>v.sellers.filter(s=>s.isPriceBot)).slice(0,5).map(s=>s.name)
      console.log(`[watch][${id}] ok variants=${data.variants.length} top3=${top.map(s=>`${s.name}:${s.price}`).join(', ')} suspectedBots=${[...new Set(suspected)].join(', ')}`)
    } catch (e:any) {
      console.error(`[watch][${id}] error:`, e?.message || e)
    }
  }
}

async function main() {
  const { ids, city, intervalSec } = parseArgs()
  if (!ids.length) { console.error('Usage: tsx scripts/price_watch.ts --ids=ID1,ID2 --city=710000000 --intervalSec=60'); process.exit(1) }
  console.log(`Price Watch: ids=${ids.join(', ')} city=${city} intervalSec=${intervalSec}`)
  // eslint-disable-next-line no-constant-condition
  while (true) {
    await tick(ids, city)
    await new Promise(r=>setTimeout(r, intervalSec*1000))
  }
}

main()


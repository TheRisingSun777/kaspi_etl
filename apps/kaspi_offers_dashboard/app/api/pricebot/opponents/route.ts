import { NextResponse } from 'next/server'
import { chromium } from 'playwright'
import { extractProductIdAndVariantFromSku } from '@/server/pricebot/sku'
import { getSettings } from '@/server/db/pricebot.settings'
import fs from 'node:fs'
import path from 'node:path'

const cache = new Map<string, { expires: number; data: any[] }>()
const TTL_MS = 180 * 1000

function logLine(line: string) {
  try {
    const dir = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'logs')
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
    const file = path.join(dir, `opponents-${new Date().toISOString().slice(0,10)}.log`)
    fs.appendFileSync(file, `${new Date().toISOString()} ${line}\n`)
  } catch {}
}

async function fetchJsonWithBackoff(url: string, tries = 3): Promise<any[] | null> {
  for (let attempt = 0; attempt < tries; attempt++) {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 6000)
    try {
      const res = await fetch(url, { headers: { accept: 'application/json, text/plain, */*' }, cache: 'no-store', signal: controller.signal })
      const status = res.status
      if (!res.ok) {
        if ((status === 429 || status >= 500) && attempt < tries - 1) {
          const wait = 250 + Math.floor(Math.random() * 500) * (attempt + 1)
          await new Promise(r => setTimeout(r, wait))
          continue
        }
        return null
      }
      const js = await res.json().catch(()=>null)
      const arr: any[] = Array.isArray(js?.data) ? js.data : Array.isArray(js?.offers) ? js.offers : Array.isArray(js) ? js : []
      return arr
    } catch (e:any) {
      const isTimeout = e?.name === 'AbortError' || /aborted|timeout/i.test(String(e?.message||''))
      if (isTimeout && attempt < tries - 1) {
        const wait = 300 + Math.floor(Math.random() * 600) * (attempt + 1)
        await new Promise(r => setTimeout(r, wait))
        continue
      }
      return null
    } finally {
      clearTimeout(timeout)
    }
  }
  return null
}

function dedupeAndSort(list: any[]): any[] {
  const map = new Map<string, any>()
  for (const s of list) {
    const key = (s.sellerId || s.sellerName || '').toString().trim().toLowerCase()
    if (!key) continue
    const price = Number(s.price || 0)
    const cur = map.get(key)
    if (!cur || (price > 0 && price < Number(cur.price||0))) {
      map.set(key, { ...s, price })
    }
  }
  return Array.from(map.values()).sort((a,b)=>Number(a.price||0)-Number(b.price||0))
}

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    let productId = String(searchParams.get('productId') || '')
    const sku = searchParams.get('sku') || ''
    const cityId = String(searchParams.get('cityId') || process.env.DEFAULT_CITY_ID || '710000000')
    const merchantId = String(searchParams.get('merchantId') || process.env.KASPI_MERCHANT_ID || '')
    if (!productId && sku) {
      const e = extractProductIdAndVariantFromSku(sku)
      if (e.productId) productId = String(e.productId)
    }
    if (!productId) return NextResponse.json({ ok: true, items: [] })

    const ck = `${productId}:${cityId}:${merchantId}`
    const now = Date.now()
    const hit = cache.get(ck)
    if (hit && hit.expires > now) return NextResponse.json({ ok: true, items: hit.data })
    if (!productId) return NextResponse.json({ ok: true, sellers: [] })

    // First attempt: Kaspi JSON endpoint with backoff
    const jsonUrl = `https://kaspi.kz/yml/offer-view/offers?productId=${encodeURIComponent(productId)}&cityId=${encodeURIComponent(cityId)}`
    const arr = await fetchJsonWithBackoff(jsonUrl)
    if (arr && arr.length) {
      const st = getSettings(merchantId)
      const ignore = new Set([...(st.globalIgnoredOpponents||[]), ...((sku?st.sku[sku]?.ignoredOpponents:[])||[])])
      const mapped = arr.map((r:any)=>({
        sellerId: String(r.merchantId || r.merchantUID || r.sellerId || ''),
        sellerName: String(r.merchantName || r.sellerName || ''),
        price: Number(r.price || r.minPrice || r.priceBase || 0),
        isYou: String(r.merchantId || r.merchantUID || '') === merchantId,
        isIgnored: ignore.has(String(r.merchantId || r.merchantUID || r.sellerId || '')),
      })).filter(s=>s.price>0)
      const sellers = dedupeAndSort(mapped)
      cache.set(ck, { expires: now + TTL_MS, data: sellers })
      logLine(`json_ok pid=${productId} city=${cityId} m=${merchantId} sellers=${sellers.length}`)
      return NextResponse.json({ ok: true, items: sellers })
    }

    // Scraper fallback only if allowed
    if (process.env.ENABLE_SCRAPE !== '1') {
      logLine(`fallback_blocked pid=${productId} city=${cityId} m=${merchantId}`)
      return NextResponse.json({ ok: true, sellers: [] })
    }

    const browser = await chromium.launch({ headless: process.env.PW_HEADLESS !== '0' })
    const context = await browser.newContext()
    const page = await context.newPage()
    await page.goto(`https://kaspi.kz/shop/p/-${productId}/?c=${cityId}`, { waitUntil: 'domcontentloaded', timeout: 25000 })
    const rows = page.locator('.sellers-table tr, .merchant-list__item, .sellers-list__item, [data-cy*="sellers"] li, .sellers-list li, .merchant__root')
    const sellers = await rows.evaluateAll((els: Element[])=>{
      const out: any[] = []
      for (const el of els) {
        const root = el as HTMLElement
        const name = (root.querySelector('.sellers-table__merchant-name') as HTMLElement)?.textContent?.trim() || ''
        const mId = (root.querySelector('[data-merchant-id]') as HTMLElement)?.getAttribute('data-merchant-id') || ''
        const priceTxt = (root.querySelector('.sellers-table__price-cell-text') as HTMLElement)?.textContent || ''
        const price = Number((priceTxt.match(/\d[\d\s]+/)?.[0]||'').replace(/\s/g,''))
        if (name && price>0) out.push({ merchantUID: mId, merchantName: name, price })
      }
      return out
    })
    await browser.close()
    const st = getSettings(merchantId)
    const ignore = new Set([...(st.globalIgnoredOpponents||[]), ...((sku?st.sku[sku]?.ignoredOpponents:[])||[])])
    const mapped = sellers.map((s:any)=>({ sellerId: String(s.merchantUID||''), sellerName: s.merchantName, price: Number(s.price||0), isYou: String(s.merchantUID||'')===merchantId, isIgnored: ignore.has(String(s.merchantUID||'')) }))
    const deduped = dedupeAndSort(mapped)
    cache.set(ck, { expires: now + TTL_MS, data: deduped })
    logLine(`scrape_ok pid=${productId} city=${cityId} m=${merchantId} sellers=${deduped.length}`)
    return NextResponse.json({ ok: true, items: deduped })
  } catch (e:any) {
    logLine(`error pid=? code=${String(e?.message||e).slice(0,80)}`)
    return NextResponse.json({ ok: true, items: [] })
  }
}



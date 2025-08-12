#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import CDP from 'chrome-remote-interface'

function ensureDir(filePath) {
  const dir = path.dirname(filePath)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
}

function toCookieHeader(cookies, cityId) {
  const parts = []
  for (const c of cookies) {
    // Only kaspi.kz domains
    if (!c || typeof c.name !== 'string') continue
    const d = String(c.domain || '')
    if (!d.includes('kaspi.kz')) continue
    parts.push(`${c.name}=${c.value}`)
  }
  // dedupe by name (last wins)
  const byName = new Map()
  for (const p of parts) {
    const [n, ...rest] = p.split('=')
    byName.set(n, `${n}=${rest.join('=')}`)
  }
  let header = Array.from(byName.values()).join('; ')
  if (!/kaspi\.storefront\.cookie\.city=/.test(header)) {
    header = header ? `${header}; kaspi.storefront.cookie.city=${cityId}` : `kaspi.storefront.cookie.city=${cityId}`
  }
  return header
}

async function main() {
  const merchantId = process.argv[2] || '30141222'
  const cityId = process.argv[3] || '710000000'
  const host = process.env.CDP_HOST || '127.0.0.1'
  const port = Number(process.env.CDP_PORT || 9222)

  let client
  try {
    client = await CDP({ host, port })
  } catch (e) {
    console.error('[cookie-grab] Could not connect to Chrome DevTools on', `${host}:${port}`)
    console.error('Start Chrome with: open -na "Google Chrome" --args --profile-directory="UNI" --remote-debugging-port=9222 https://kaspi.kz/shop/p/-131138247/?c=710000000')
    process.exit(2)
  }
  const { Network } = client
  await Network.enable()
  const all = await Network.getAllCookies()
  const header = toCookieHeader(all.cookies || [], cityId)
  await client.close()

  if (!header) {
    console.error('[cookie-grab] No kaspi.kz cookies found. Make sure Chrome is opened with the UNI profile and you are logged in, then reload the product page.');
    process.exit(3)
  }

  const file = path.join(process.cwd(), 'server', 'merchant', `${merchantId}.cookie.json`)
  ensureDir(file)
  fs.writeFileSync(file, JSON.stringify({ cookie: header }, null, 2))
  console.log('[cookie-grab] Saved cookie header to', file)
}

main().catch((e)=>{ console.error(e); process.exit(1) })



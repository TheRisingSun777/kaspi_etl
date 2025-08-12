#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import { getCookies } from 'chrome-cookies-secure'

function ensureDir(filePath) {
  const dir = path.dirname(filePath)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
}

function ensureCityCookie(header, cityId) {
  const base = String(header || '')
  return /kaspi\.storefront\.cookie\.city=/.test(base)
    ? base
    : (base ? base + '; ' : '') + `kaspi.storefront.cookie.city=${cityId}`
}

async function main() {
  const merchantId = process.argv[2] || '30141222'
  const cityId = process.argv[3] || '710000000'

  const url = 'https://kaspi.kz'
  const opts = { profile: 'Profile 2' }
  const header = await new Promise((resolve, reject) => {
    getCookies(url, 'header', (err, cookie) => {
      if (err) return reject(err)
      resolve(cookie)
    }, opts)
  }).catch((e) => {
    console.error('[cookie-grab:profile2] error reading Chrome cookies:', e?.message || e)
    return ''
  })

  const finalHeader = ensureCityCookie(header || '', cityId)
  if (!finalHeader) {
    console.error('[cookie-grab:profile2] No cookies found for', url, '(Profile 2). Ensure Chrome Profile 2 is logged in and try again.')
    process.exit(2)
  }

  const file = path.join(process.cwd(), 'server', 'merchant', `${merchantId}.cookie.json`)
  ensureDir(file)
  fs.writeFileSync(file, JSON.stringify({ cookie: finalHeader }, null, 2))
  console.log('[cookie-grab:profile2] Saved cookie header to', file)
}

main().catch((e)=>{ console.error(e); process.exit(1) })



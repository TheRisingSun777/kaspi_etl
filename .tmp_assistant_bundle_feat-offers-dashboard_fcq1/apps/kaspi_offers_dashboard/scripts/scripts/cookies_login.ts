import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'

async function main() {
  const browser = await chromium.launch({ headless: false, slowMo: 100 })
  const context = await browser.newContext()
  const page = await context.newPage()
  console.log('Open this page and login, then press Enter here...')
  await page.goto('https://mc.shop.kaspi.kz/', { waitUntil: 'domcontentloaded' })
  process.stdin.setRawMode(true)
  process.stdin.resume()
  process.stdin.on('data', async () => {
    const cookies = await context.cookies()
    const map: Record<string,string> = {}
    for (const c of cookies) map[c.name] = c.value
    const cookieStr = [map['mc-session'] ? `mc-session=${map['mc-session']}` : '', map['mc-sid'] ? `mc-sid=${map['mc-sid']}` : ''].filter(Boolean).join('; ')
    const file = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'db', 'merchant.cookie.json')
    fs.mkdirSync(path.dirname(file), { recursive: true })
    fs.writeFileSync(file, JSON.stringify({ cookie: cookieStr, updatedAt: new Date().toISOString() }, null, 2))
    console.log('Saved to', file)
    await browser.close()
    process.exit(0)
  })
}

main().catch((e)=>{ console.error(e); process.exit(1) })



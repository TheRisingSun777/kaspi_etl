#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

async function main(){
  const merchantId = process.argv[2]
  if (!merchantId) { console.error('Usage: login.mjs <merchantId>'); process.exit(1) }
  const browser = await chromium.launch({ headless: false })
  const context = await browser.newContext()
  const page = await context.newPage()
  console.log('Open Kaspi merchant login page and sign in, then press Enter here...')
  await page.goto('https://kaspi.kz/', { waitUntil:'domcontentloaded' })
  await new Promise(res=>{ process.stdin.resume(); process.stdin.on('data', ()=>res()) })
  const cookies = await context.cookies()
  await browser.close()
  const dir = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'cookies')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  const file = path.join(dir, `${merchantId}.json`)
  fs.writeFileSync(file, JSON.stringify({ cookies }, null, 2))
  console.log('Saved to', file)
}

main().catch((e)=>{ console.error(e); process.exit(1) })



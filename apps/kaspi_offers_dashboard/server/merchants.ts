import fs from 'node:fs'
import path from 'node:path'

export type Merchant = { merchantId: string; label: string; cityId?: number; cookieFile?: string; apiKey?: string }

const FILE = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'db', 'merchants.json')

function ensureDir() { const dir = path.dirname(FILE); if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true }) }

export function readMerchants(): Merchant[] {
  try {
    const raw = fs.readFileSync(FILE, 'utf-8')
    const js = JSON.parse(raw)
    return Array.isArray(js) ? js : []
  } catch {
    return []
  }
}

export function writeMerchants(list: Merchant[]) {
  ensureDir()
  fs.writeFileSync(FILE, JSON.stringify(list, null, 2))
}



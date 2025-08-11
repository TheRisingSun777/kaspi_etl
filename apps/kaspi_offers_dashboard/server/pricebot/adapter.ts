import fs from 'node:fs'
import path from 'node:path'

export type PriceUpdate = { variantId: string; newPrice: number; reason: string }

export interface MerchantWriter {
  applyPrices(updates: PriceUpdate[], opts?: { dryRun?: boolean }): Promise<{ ok: boolean; applied: number; errors?: string[]; file?: string }>
}

export class CsvWriter implements MerchantWriter {
  async applyPrices(updates: PriceUpdate[], _opts?: { dryRun?: boolean }) {
    try {
      const dir = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'data_raw', 'pricebot')
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      const ts = new Date().toISOString().replace(/[:.]/g, '-')
      const file = path.join(dir, `apply_${ts}.csv`)
      const header = 'variantId,newPrice,reason,ts\n'
      const rows = updates.map(u => [u.variantId, u.newPrice, JSON.stringify(u.reason), ts].join(',')).join('\n')
      fs.writeFileSync(file, header + rows)
      return { ok: true, applied: updates.length, file }
    } catch (e:any) {
      return { ok:false, applied: 0, errors: [String(e?.message||e)] }
    }
  }
}

export const defaultWriter: MerchantWriter = new CsvWriter()



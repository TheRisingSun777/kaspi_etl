import type { Row } from '@/lib/pricebot/types'
import type { PriceUpdate } from './adapter'

export function computeUpdate(row: Row, opts: { ignoreMerchants?: string[] } = {}): PriceUpdate | null {
  if (!row.active) return null
  if ((row.stock || 0) <= 0) return null
  const sellers = (row.sellers||[]).filter(s => !opts.ignoreMerchants?.includes(String(s.name||'')))
  if (!sellers.length) return null
  const prices = sellers.map(s=>Number(s.price||0)).filter(n=>Number.isFinite(n))
  if (!prices.length) return null
  const minComp = Math.min(...prices)
  const step = Number(row.step||1)
  const floor = Number(row.min||0)
  const ceil = Number(row.max||0)
  let target = Math.round(minComp - step)
  if (floor>0) target = Math.max(floor, target)
  if (ceil>0) target = Math.min(ceil, target)
  if (!Number.isFinite(target) || target<=0) return null
  const reason = `minComp=${minComp} step=${step} floor=${floor} ceil=${ceil}`
  return { variantId: row.variantId || row.masterId, newPrice: target, reason }
}



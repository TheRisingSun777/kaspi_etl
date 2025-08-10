// server/pricebot/logic.ts
export type RepriceInput = {
  ourPrice: number
  minPrice: number
  maxPrice: number
  step: number
  competitors: Array<{ seller: string; price: number }>
}

export function isBotDense(competitors: Array<{ price: number }>, min: number): boolean {
  const close = competitors.filter(c => Math.abs(c.price - min) <= 3)
  return close.length >= 3
}

export function computeTargetPrice(inp: RepriceInput): { target: number; reason: string } {
  const { ourPrice, minPrice, maxPrice, step, competitors } = inp
  const compMin = competitors.length ? Math.min(...competitors.map(c => c.price)) : Infinity
  if (!Number.isFinite(compMin)) {
    // No competitors → aim to ceiling
    return { target: clamp(maxPrice, minPrice, maxPrice), reason: 'no_competitors' }
  }
  // If bot-dense within ±3 KZT of compMin, match not undercut
  const targetBase = isBotDense(competitors, compMin) ? compMin : (compMin - step)
  let target = clamp(targetBase, minPrice, maxPrice)
  // Only meaningful change
  if (Math.abs(target - ourPrice) < step) target = ourPrice
  // When matching, round to nearest integer to avoid 1099 vs 1100 drift if compMin was float
  target = Math.round(target)
  return { target, reason: isBotDense(competitors, compMin) ? 'match_bot_dense' : 'undercut' }
}

function clamp(v:number, lo:number, hi:number){ return Math.max(lo, Math.min(hi, v)) }



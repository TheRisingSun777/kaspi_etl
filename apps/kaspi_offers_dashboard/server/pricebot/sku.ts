export function extractProductIdAndVariantFromSku(sku: string): { productId?: number; variant?: string } {
  if (!sku) return {}
  // Try to capture numeric product id between underscores or at end e.g. ..._121213226_ or ...-121213226)
  const m = sku.match(/[_-]([0-9]{6,12})(?:[_)\s]|$)/)
  const productId = m ? Number(m[1]) : undefined
  // Variant: last parenthesized token, e.g. ..._(XL)
  const vm = sku.match(/\(([^)]+)\)\s*$/)
  const variant = vm ? vm[1] : undefined
  return { productId, variant }
}

export function buildShopLink(productId?: number, city?: string): string | undefined {
  if (!productId) return undefined
  return `https://kaspi.kz/shop/p/-${productId}/?c=${city || process.env.DEFAULT_CITY_ID || '710000000'}`
}



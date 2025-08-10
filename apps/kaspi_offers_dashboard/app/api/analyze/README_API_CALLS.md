HTTP requests used by the server route (server-side only)

1) Merchant API (our data), product name best-effort:

Request:

```
GET https://kaspi.kz/shop/api/v2/offers?masterProductId={MASTER_ID}
Headers:
  Accept: application/json
  X-Auth-Token: {KASPI_TOKEN}
```

2) Public offers (competitors), variant sellers list (best-effort, subject to change):

Request (try):

```
GET https://kaspi.kz/yml/offer-view/offers/{PRODUCT_ID}?cityId={CITY_ID}
Headers:
  Accept: application/json, text/plain, */*
  User-Agent: Mozilla/5.0 (compatible; KaspiOffersInsight/1.0)
```

Fallback: fetch HTML page and parse embedded JSON:

```
GET https://kaspi.kz/shop/p/{PRODUCT_ID}/?c={CITY_ID}
Headers:
  User-Agent: Mozilla/5.0 (compatible; KaspiOffersInsight/1.0)
```

Returned JSON is normalized to AnalyzeResponse shape.


Input JSON

```
{ "masterProductId": "121207970", "cityId": "710000000" }
```

Output JSON (shape)

```
{
  masterProductId: string,
  productName?: string,
  cityId: string,
  productImageUrl?: string,
  attributes?: { sizesAll?: string[], colorsAll?: string[] },
  variantMap?: Record<string, { color?: string; size?: string; name?: string }>,
  ratingCount?: number,
  variants: Array<{
    productId: string,
    label: string,
    variantColor?: string,
    variantSize?: string,
    rating?: { avg?: number; count?: number },
    sellersCount: number,
    sellers: Array<{ name: string; price: number; deliveryDate?: string; isPriceBot?: boolean }>,
    stats?: { min?: number; median?: number; max?: number; spread?: number; stddev?: number; predictedMin24h?: number; predictedMin7d?: number; stabilityScore?: number }
  }>,
  uniqueSellers?: number,
  analytics?: { avgSpread?: number; medianSpread?: number; maxSpread?: number; botShare?: number; attractivenessIndex?: number; stabilityScore?: number; bestEntryPrice?: number }
}
```


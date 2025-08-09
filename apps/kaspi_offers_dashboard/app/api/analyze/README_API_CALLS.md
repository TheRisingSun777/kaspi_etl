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



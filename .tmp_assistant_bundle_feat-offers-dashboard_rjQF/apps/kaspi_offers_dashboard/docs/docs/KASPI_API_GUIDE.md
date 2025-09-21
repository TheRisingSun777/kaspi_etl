Kaspi APIs — Practical Guide for This App

This app talks to two different Kaspi API families. Don’t mix them:
	1.	Merchant Cabinet (MC) API — private, used in your Kaspi merchant UI
	•	Base: https://mc.shop.kaspi.kz
	•	Auth: cookies only (mc-session, mc-sid)
	•	Headers required:
	•	x-auth-version: 3
	•	Origin: https://kaspi.kz
	•	Referer: https://kaspi.kz
	•	typical browser headers (Accept: application/json, text/plain, */*, Accept-Language, User-Agent)
	•	CORS: MC forbids browser-origin calls. Always call from our Next.js server routes.
	2.	Shop API — public partner API for catalog, product import, orders, classification
	•	Base: https://kaspi.kz/shop/api
	•	Auth: X-Auth-Token: <your_api_token>
	•	Formats: regular JSON for products/classification; JSON:API for v2 Orders.

✅ Rule of thumb:
	•	Listing your store’s offers and repricing => MC API (cookies).
	•	Importing products, category attributes, orders => Shop API (X‑Auth‑Token).
If you point MC paths at the Shop base (or vice versa), you’ll get 404s.

⸻

Environment variables used by this app

We keep both bases available but route correctly per feature:
# Merchant basics
KASPI_MERCHANT_ID=30141222

# MC API (listing, repricing)
KASPI_MERCHANT_API_BASE=https://mc.shop.kaspi.kz
KASPI_MERCHANT_COOKIES=mc-session=REPLACE_ME; mc-sid=REPLACE_ME

# Shop API (orders, product import, classification)
KASPI_SHOP_API_BASE=https://kaspi.kz/shop/api
KASPI_MERCHANT_API_KEY=REPLACE_ME   # value for X-Auth-Token

# Default city
CITY_ID=710000000
In dev, use .env.local (never commit). In repo, keep .env.example with placeholders.

⸻

What our internal API routes do (use these in the UI)

Always use the app’s internal routes from the front‑end. They normalize responses and hide auth.
	•	GET /api/debug/merchant
Quick check that MC cookies work. Returns counts like published, archived, etc.
	•	GET /api/merchant/offers?p=0&l=50&available=true
Lists your live offers. The upstream MC response can vary its array key (items, content, data, or a top‑level array).
Our server picks the right one automatically and normalizes each item to:
{ sku: string, name: string, productId: number|null, price: number }
	•	GET /api/pricebot/offers
Merges the merchant offers with local settings + derived fields:
{
  name: string,
  sku: string,
  productId: number|null,
  price: number,
  stock: number,
  opponents: number,
  settings: {
    min: number, max: number, step: number, interval: number,
    active: boolean, ignoreSellers: string[]
  }
}
	•	POST /api/pricebot/reprice
Body:
{ "sku": "CL_OC_...", "price": 8699, "cityId": "710000000" }
Proxies to the MC “discount” endpoint (see below), returns MC payload.

	•	GET /api/pricebot/settings + POST /api/pricebot/settings
Reads/writes server/db/pricebot.json with per‑SKU settings (min/max/step/interval/active/ignoreSellers).
The file is git‑ignored so you can store real working data locally.
	•	GET /api/pricebot/opponents?productId=...&cityId=...
Returns competitor sellers for a product (see “Opponents” below for strategy).

⸻

Upstream MC API (cookies): endpoints we actually hit

1) List merchant offers (shape varies)
	•	Base: https://mc.shop.kaspi.kz
	•	Path: merchant cabinet “offers list” endpoint (Kaspi changes internal paths; our server code discovers the array under items|content|data|[...]).
	•	Query params we use:
	•	p (page), l (limit)
	•	available=true (or a=true), lowStock=false, notSpecifiedStock=false
	•	optional: t (search text), c (category)
	•	Headers required (server side only):
    Cookie: mc-session=...; mc-sid=...
x-auth-version: 3
Origin: https://kaspi.kz
Referer: https://kaspi.kz
Accept: application/json, text/plain, */*
Our server normalizes to { sku, name, productId, price } and fills stock with 1 by default when MC doesn’t return quantity.

2) Reprice (aka “discount”)
	•	URL: POST https://mc.shop.kaspi.kz/price/trends/api/v1/mc/discount
	•	Headers: same cookie + x-auth-version: 3 + Origin/Referer
	•	JSON body example:
    {
  "merchantUID": "30141222",
  "merchantSKU": "CL_OC_MEN_PRINT51_BLACK_112128130_50_(XL)",
  "entries": [{ "city": "710000000", "price": 8699 }]
}
	•	Notes: MC enforces minimum discount rules and history. You may see NOT_ENOUGH_HISTORY with fields like firstSuitableDate. Our UI shows that back to the user.

⸻

Upstream Shop API (X‑Auth‑Token): endpoints you may need

These do not replace MC endpoints. Use them for catalog/attributes/import/orders, not for listing your own offers or repricing.

3) Product import (create/update product attributes & images)
	•	URL: POST https://kaspi.kz/shop/api/products/import
	•	Headers:
X-Auth-Token: <token>
Accept: application/json
Content-Type: application/json
	•	Body (array of products):
    [
  {
    "sku": "TestSKU",
    "title": "Product name",
    "brand": "Brand",
    "category": "Master - Exercise notebooks",
    "description": "Short description",
    "attributes": [
      { "code": "Exercise notebooks*...*type", "value": "тетрадь-блокнот" },
      { "code": "Exercise notebooks*...*number of sheets", "value": 48 }
    ],
    "images": [{ "url": "https://cdn-kaspi.kz/path/to.jpg" }]
  }
]
	•	Response: { "code": "...", "status": "UPLOADED" }

4) Classification — attributes for a category
	•	URL: GET https://kaspi.kz/shop/api/products/classification/attributes?c=<CategoryCode>
	•	Headers: X-Auth-Token: <token>, Accept: application/json
	•	Response: list of attributes { code, type, multiValued, mandatory }

5) Classification — allowed values for a specific attribute
	•	URL:
GET https://kaspi.kz/shop/api/products/classification/attribute/values?c=<CategoryCode>&a=<AttributeCode>
	•	Headers: X-Auth-Token: <token>, Accept: application/json
	•	Response: list of { code, name } values

6) Import schema (JSON Schema for products/import)
	•	URL: GET https://kaspi.kz/shop/api/products/import/schema
	•	Headers: X-Auth-Token: <token>, Accept: application/json

7) Orders (JSON:API)
	•	URL base: https://kaspi.kz/shop/api/v2/orders
	•	Headers:
Content-Type: application/vnd.api+json
X-Auth-Token: <token>
	•	Example (status update request body):
    {
  "data": {
    "type": "orders",
    "id": "ordersID",
    "attributes": {
      "code": "ordercode",
      "status": "CANCELLED",
      "cancellationReason": "BUYER_CANCELLATION_BY_MERCHANT"
    }
  }
}
Opponents (competitor sellers) — how we get them

Kaspi does not expose a stable public JSON for competitor price lists per product via Shop API. Options:
	1.	Storefront scrape (recommended fallback):
Fetch the public product page on the server (include cityId) and parse the embedded JSON that lists offers. Sort by price, map {sellerName, merchantId, price, isOurStore}. This is what our /api/pricebot/opponents route will do if no private MC JSON is available.
	2.	MC internal JSON (if discovered for your tenant):
Some merchant accounts expose JSON used by their cabinet for “opponent” views. If available and stable, prefer that on the server with cookie auth.

Either way, the UI shows an “Opponents” count; clicking opens a modal with a sorted seller list and toggles to ignore specific merchants. The selected merchants are stored in pricebot.json under ignoreSellers and respected by the repricer.

⸻

Common pitfalls (seen in your setup)
	•	404 when using API key on MC endpoints. API keys only work on the Shop API (kaspi.kz/shop/api). MC list/reprice require cookie auth.
	•	MC requests must be server-side with Origin/Referer set to https://kaspi.kz and x-auth-version: 3.
	•	Array key drift: MC list sometimes returns arrays under items, sometimes content, sometimes data, and sometimes a raw array. Our server-side picker already handles this.
	•	Missing productId: some offers return productId: 0 or null. Opponents lookup will attempt storefront search by SKU as a fallback.
	•	City ID matters for price competition and repricing entries (we use 710000000 by default).

Your current /pricebot table shows normalized items coming from the MC list via our server, so the data path is correct.  ￼

⸻

Test cURL snippets (redact secrets)

Check MC auth (cookies)
curl -i 'http://localhost:3001/api/debug/merchant'
List offers (normalized)
curl -s 'http://localhost:3001/api/merchant/offers?p=0&l=50' | jq .
Reprice (discount) via our server proxy
curl -s -X POST 'http://localhost:3001/api/pricebot/reprice' \
  -H 'Content-Type: application/json' \
  -d '{"sku":"CL_OC_MEN_PRINT51_BLACK_112128130_50_(XL)","price":8699,"cityId":"710000000"}' | jq .
  Data models we persist (server/db/pricebot.json)
  type PricebotSettings = {
  [sku: string]: {
    active: boolean
    min: number
    max: number
    step: number            // KZT increment
    interval: number        // minutes; UI: fastest..15
    ignoreSellers: string[] // merchant ids to ignore globally for this SKU
  }
}

⸻

How the UI should behave (acceptance)
	•	Toggle Pricebot ON/OFF per row (writes settings).
	•	Stock column shows real stock when available; otherwise fallback 1.
	•	Min/Max/Step/Interval editable with debounce, persisted.
	•	Opponents count clickable → modal: sorted by price, toggles to ignore specific sellers.
	•	Top bar: global ignore list input to add merchant IDs to exclude for all items.
	•	Sorting & filtering across columns.
	•	Export XLSX/CSV and Import XLSX/CSV with shape:
SKU, model, brand, price, PP1, preorder, min_price, max_price, step, shop_link, pricebot_status.
	•	Design: modern dark theme, gentle gradients, smooth toggles, modal animations, Apple‑like polish.

⸻

Final reminders
	•	Never commit secrets (.env.local, cookies, tokens).
	•	Keep progress in apps/kaspi_offers_dashboard/CURSOR_PROGRESS.md.
	•	If MC changes the list JSON shape again, update only the array-picker logic in the server route.
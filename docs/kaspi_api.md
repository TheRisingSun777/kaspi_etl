# Kaspi API Documentation (Merchant)

## Authentication & Required Headers
- Base URL: `https://kaspi.kz/shop/api/v2`
- Headers (always include):
  - `X-Auth-Token: {your_token}`
  - `Accept: application/vnd.api+json;charset=UTF-8`

## Pagination & Filtering
- Pagination uses JSON:API style:
  - `page[number]=1`
  - `page[size]=50`
- Some resources (e.g., `orders`) require date filters:
  - `filter[orders][creationDate][$ge]=YYYY-MM-DDTHH:MM:SSZ`
  - `filter[orders][creationDate][$le]=YYYY-MM-DDTHH:MM:SSZ`
- Optional filters:
  - `filter[orders][state]=NEW|ASSEMBLE|ACCEPTED_BY_MERCHANT|CANCELLED|COMPLETED|...`
- Includes (expand related data):
  - `include[orders]=user` (contact info)

## Endpoints (most used)

### Orders (list)
GET `/shop/api/v2/orders`

Example: last 24 hours, small page, include user

```bash
curl -s \
  -H 'X-Auth-Token: $KASPI_TOKEN' \
  -H 'Accept: application/vnd.api+json;charset=UTF-8' \
  'https://kaspi.kz/shop/api/v2/orders?\
    filter[orders][creationDate][$ge]=2025-08-09T00:00:00Z&\
    filter[orders][creationDate][$le]=2025-08-10T23:59:59Z&\
    page[number]=1&page[size]=5&\
    include[orders]=user'
```

Response (shape):

```json
{
  "data": [
    {
      "type": "orders",
      "id": "123456789",
      "attributes": {
        "state": "NEW",
        "creationDate": "2025-08-10T10:21:34Z",
        "deliveryType": "PICKUP",
        "grandTotal": 12990,
        "items": [
          { "sku": "SKU-001", "name": "Rashguard Black XL", "quantity": 1, "unitPrice": 12990 }
        ]
      }
    }
  ],
  "meta": { "totalPages": 10 },
  "links": { "self": "...", "next": "..." }
}
```

Notes:
- If you receive `400 Required filter [orders][creationDate][$ge] is empty`, add both `$ge` and `$le` filters.
- If you receive `406 Not Acceptable`, set the `Accept` header to `application/vnd.api+json;charset=UTF-8`.

### Update Price (bulk)
PUT `/shop/api/v2/prices`

Payload (example):

```json
{
  "data": [
    { "type": "prices", "id": "SKU-001", "attributes": { "price": 12990 } },
    { "type": "prices", "id": "SKU-002", "attributes": { "price": 11990 } }
  ]
}
```

### Update Stock (bulk)
PUT `/shop/api/v2/stocks`

Payload (example):

```json
{
  "data": [
    { "type": "stocks", "id": "SKU-001", "attributes": { "available": 5 } }
  ]
}
```

## Response Format (JSON:API)
```json
{
  "data": [...],
  "meta": {...},
  "links": {...}
}
```

## Example HTML (rendering current prices)
Below is a minimal HTML snippet showing how to render a small table of items and current prices (e.g., sale items) from a JSON response you fetched server‑side. Replace the sample rows with your parsed response. This is purely a display example.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Sale Items</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 16px; }
    table { border-collapse: collapse; width: 680px; }
    th, td { border: 1px solid #e5e7eb; padding: 8px 10px; font-size: 14px; }
    th { background: #f9fafb; text-align: left; }
    .price { font-variant-numeric: tabular-nums; }
    .sale { color: #b91c1c; font-weight: 600; }
  </style>
  <script>
    // Example data you might construct from your API response
    const items = [
      { sku: 'SKU-001', name: 'Rashguard Black XL', price: 12990, oldPrice: 14990, stock: 7 },
      { sku: 'SKU-002', name: 'Rashguard Black L',  price: 11990, oldPrice: 12990, stock: 3 },
    ];
    function fmt(n){ return new Intl.NumberFormat('ru-KZ').format(n) + ' ₸' }
    window.addEventListener('DOMContentLoaded', () => {
      const tbody = document.querySelector('#rows');
      for (const it of items) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${it.sku}</td>
          <td>${it.name}</td>
          <td class="price sale">${fmt(it.price)}</td>
          <td class="price" style="text-decoration:line-through; opacity:.6">${fmt(it.oldPrice)}</td>
          <td>${it.stock}</td>
        `;
        tbody.appendChild(tr);
      }
    });
  </script>
  </head>
  <body>
    <h1>Sale Items — Current Prices</h1>
    <table>
      <thead>
        <tr>
          <th>SKU</th>
          <th>Item</th>
          <th>Current Price</th>
          <th>Old Price</th>
          <th>Stock</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </body>
</html>
```

## Rate Limits & Reliability
- Respect rate limits; back off on 429/5xx.
- Keep retries with exponential backoff.
- For competitor prices, use the server scraper (our Next.js dashboard) — the merchant API does not expose competitor offer prices.

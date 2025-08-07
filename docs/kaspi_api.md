# Kaspi API Documentation

## Authentication
- **Header**: `X-Auth-Token: {your_token}`
- **Base URL**: `https://kaspi.kz/shop/api/v2`

## Endpoints

### Products
- **POST** `/shop/api/v2/products/create` - Create/update product
- **GET** `/shop/api/v2/products` - List products

### Pricing & Stock
- **PUT** `/shop/api/v2/prices` - Bulk price update
- **PUT** `/shop/api/v2/stocks` - Bulk stock update

### Orders
- **GET** `/shop/api/v2/orders?filter[orders][state]=NEW` - Get new orders
  - Add `include[orders]=user` to get customer phone numbers
- **POST** `/shop/api/v2/orders` - Update order status
  - Status values: `ACCEPTED_BY_MERCHANT`, `ASSEMBLE`, `CANCELLED`

### Kaspi Delivery
- **POST** `/shop/api/v2/orders` - Set `numberOfSpace` in `ASSEMBLE` status
- **GET** `/shop/api/v2/orders/{id}/label` - Fetch shipping label PDF

## Response Formats
All responses return JSON with standard structure:
```json
{
  "data": [...],
  "meta": {...},
  "links": {...}
}
```

## Rate Limits
- Monitor response headers for rate limit information
- Implement exponential backoff on failures

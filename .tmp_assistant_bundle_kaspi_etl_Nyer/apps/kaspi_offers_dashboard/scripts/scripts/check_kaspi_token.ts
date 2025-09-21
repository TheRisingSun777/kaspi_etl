/*
  Usage:
    1) Create apps/kaspi_offers_dashboard/.env.local with KASPI_TOKEN=...
    2) pnpm tsx scripts/check_kaspi_token.ts
*/
import dotenv from 'dotenv'
// Prefer .env.local (Next.js convention), fallback to .env
dotenv.config({ path: '.env.local' })
dotenv.config()

async function main() {
  const token = process.env.KASPI_TOKEN
  if (!token) {
    console.error('KASPI_TOKEN is missing. Create .env.local with KASPI_TOKEN=...')
    process.exit(1)
  }

  const urls = [
    // Orders list (paginated, safe):
    'https://kaspi.kz/shop/api/v2/orders?page[number]=1&page[size]=1',
    // Orders NEW state (safe):
    'https://kaspi.kz/shop/api/v2/orders?filter[orders][state]=NEW&page[number]=1&page[size]=1&include[orders]=user',
  ]
  for (const url of urls) {
    console.log('->', url)
    const res = await fetch(url, {
      headers: {
        'X-Auth-Token': token,
        'Accept': 'application/vnd.api+json;charset=UTF-8',
      },
    })
    const text = await res.text()
    console.log('HTTP', res.status)
    console.log(text.slice(0, 200))
    console.log('')
  }
}

main().catch((e) => {
  console.error('Error:', e?.message || e)
  process.exit(1)
})



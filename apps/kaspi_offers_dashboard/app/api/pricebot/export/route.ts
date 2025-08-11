import { NextResponse } from 'next/server'
import { getMerchantId, mcFetch } from '@/lib/kaspi/client'
import ExcelJS from 'exceljs'
import { getSettings } from '@/server/db/pricebot.settings'

export const runtime = 'nodejs'

function toRows(items: any[], merchantId: string) {
  const st = getSettings(merchantId)
  return items.map((it:any)=>{
    const price = Number(it.price ?? 0)
    const sku = String(it.sku||'')
    const item = sku ? st.sku[sku] : undefined
    const min = Number(item?.minPrice ?? 0)
    const max = Number(item?.maxPrice ?? 0)
    return {
      SKU: sku,
      model: '',
      brand: '',
      price,
      PP1: '',
      preorder: '',
      min_price: min || price || '',
      max_price: max || price || '',
      step: Number(item?.stepKzt ?? 1),
      shop_link: it.productId ? `https://kaspi.kz/shop/p/-${it.productId}/?c=${process.env.DEFAULT_CITY_ID || '710000000'}` : `https://kaspi.kz/shop/search/?text=${encodeURIComponent(it.sku)}`,
      pricebot_status: item?.active ? 'on' : 'off',
    }
  })
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const format = (searchParams.get('format') || 'csv').toLowerCase()
  try {
    const merchantId = String(searchParams.get('merchantId') || searchParams.get('storeId') || process.env.KASPI_MERCHANT_ID || '')
    const m = getMerchantId()
    // Use the same list endpoint as the table. If 400/401 fallback to smaller page length.
    let res = await mcFetch(`/bff/offer-view/list?m=${m}&p=0&l=100&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`)
    const js = await res.json()
    let arr: any[] = Array.isArray(js?.items) ? js.items : Array.isArray(js?.data) ? js.data : Array.isArray(js?.content) ? js.content : []
    if (!arr.length) {
      res = await mcFetch(`/bff/offer-view/list?m=${m}&p=0&l=20&available=true&t=&c=&lowStock=false&notSpecifiedStock=false`)
      const js2 = await res.json()
      arr = Array.isArray(js2?.items) ? js2.items : Array.isArray(js2?.data) ? js2.data : Array.isArray(js2?.content) ? js2.content : []
    }
    const items = arr.map((o:any)=>{
      const sku = o.merchantSku || o.sku || o.offerSku || o.id || ''
      let productId = Number(o.variantProductId ?? o.productId ?? o.variantId ?? 0)
      const shopLink: string | undefined = o.shopLink || o.productLink || o.link || undefined
      if ((!productId || Number.isNaN(productId)) && typeof shopLink === 'string') {
        const m = shopLink.match(/-(\d+)\/?$/)
        if (m) productId = Number(m[1])
      }
      return {
        sku,
        price: Number(o.price ?? o.currentPrice ?? o.offerPrice ?? o.value ?? 0),
        productId,
        settings: undefined,
      }
    })

    const rows = toRows(items, merchantId)

    if (format === 'xlsx') {
      const wb = new ExcelJS.Workbook()
      const ws = wb.addWorksheet('pricebot')
      const headers = ['SKU','model','brand','price','PP1','preorder','min_price','max_price','step','shop_link','pricebot_status']
      ws.addRow(headers)
      rows.forEach(r=>ws.addRow(headers.map(h=>(r as any)[h])))
      const buf = await wb.xlsx.writeBuffer()
      return new NextResponse(buf as any, { headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename="pricebot.xlsx"' } })
    }

    const headers = ['SKU','model','brand','price','PP1','preorder','min_price','max_price','step','shop_link','pricebot_status']
    const csv = [headers.join(','), ...rows.map(r=>headers.map(h=>String((r as any)[h] ?? '')).join(','))].join('\n')
    return new NextResponse(csv, { headers: { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="pricebot.csv"' } })
  } catch (e:any) {
    return NextResponse.json({ ok:false, error: String(e?.message||e) }, { status: 500 })
  }
}



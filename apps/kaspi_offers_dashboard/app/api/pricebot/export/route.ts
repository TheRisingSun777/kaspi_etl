import { NextResponse } from 'next/server'
import { getMerchantId, mcFetch } from '@/lib/kaspi/client'
import ExcelJS from 'exceljs'
import { getItemSettingsOrDefault } from '@/server/db/pricebot.store'

function toRows(items: any[]) {
  return items.map((it:any)=>({
    SKU: it.sku,
    model: '',
    brand: '',
    price: it.price ?? '',
    PP1: '',
    preorder: '',
    min_price: it.settings?.min ?? '',
    max_price: it.settings?.max ?? '',
    step: it.settings?.step ?? '',
    shop_link: '',
    pricebot_status: it.settings?.active ? 'on' : 'off',
  }))
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const format = (searchParams.get('format') || 'csv').toLowerCase()
  const m = getMerchantId()
  const res = await mcFetch(`/bff/offer-view/list?m=${m}&p=0&l=200&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`)
  const js = await res.json()
  const arr: any[] = Array.isArray(js?.items) ? js.items : Array.isArray(js?.data) ? js.data : []
  const items = arr.map((o:any)=>{
    const sku = o.merchantSku || o.sku || o.offerSku || o.id || ''
    return {
      sku,
      price: Number(o.price ?? o.currentPrice ?? o.offerPrice ?? o.value ?? 0),
      productId: Number(o.variantProductId ?? o.productId ?? o.variantId ?? 0),
      settings: sku ? getItemSettingsOrDefault(sku) : undefined,
    }
  })

  const rows = toRows(items)

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
}



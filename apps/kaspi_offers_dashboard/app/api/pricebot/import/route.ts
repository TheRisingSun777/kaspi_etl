import { NextResponse } from 'next/server'
import { upsertSettings as upsertV2 } from '@/server/db/pricebot.settings'
import formidable from 'formidable'
import fs from 'node:fs'
import ExcelJS from 'exceljs'

export const dynamic = 'force-dynamic'

export async function POST(req: Request) {
  try {
    const url = new URL(req.url)
    const dryRun = url.searchParams.get('dryRun') !== 'false'
    const storeId = url.searchParams.get('storeId') || url.searchParams.get('merchantId') || ''
    // formidable expects Node request; Next provides web Request; we can buffer
    const buf = Buffer.from(await req.arrayBuffer())
    const contentType = req.headers.get('content-type') || ''
    const form = formidable({ multiples: false })
    const files: any = await new Promise((resolve, reject) => {
      form.parse({ headers: { 'content-type': contentType } } as any, (err, fields, files) => {
        if (err) reject(err); else resolve({ fields, files })
      })
    }).catch(()=>null)
    // Fallback: try reading as single buffer (not full formidable in edge env). We'll support only one file in body
    let rows: any[] = []
    try {
      // try parse as CSV
      const text = buf.toString('utf8')
      if (/,|;|\t/.test(text.split('\n')[0] || '')) {
        const lines = text.split(/\r?\n/).filter(Boolean)
        const header = lines.shift()!.split(',').map(s=>s.trim().toLowerCase())
        const idx = (name:string)=>header.indexOf(name)
        for (const line of lines) {
          const cols = line.split(',')
          rows.push({
            sku: cols[idx('sku')] || cols[0],
            min: Number(cols[idx('min_price')]),
            max: Number(cols[idx('max_price')]),
            step: Number(cols[idx('step')]),
            active: /on|true|1/i.test(cols[idx('pricebot_status')] || ''),
          })
        }
      } else {
        // xlsx
        const wb = new ExcelJS.Workbook()
        await wb.xlsx.load(buf)
        const ws = wb.worksheets[0]
        const header = ws.getRow(1).values as any[]
        const headerMap: Record<string, number> = {}
        header.forEach((v, i)=>{ if (typeof v === 'string') headerMap[v.toLowerCase()] = i })
        ws.eachRow((row, rowNumber)=>{
          if (rowNumber === 1) return
          const get = (name:string)=>row.getCell(headerMap[name] || 0).value as any
          rows.push({
            sku: String(get('sku') || ''),
            min: Number(get('min_price') || 0),
            max: Number(get('max_price') || 0),
            step: Number(get('step') || 0),
            active: /on|true|1/i.test(String(get('pricebot_status') || '')),
          })
        })
      }
    } catch {}

    const changes: any[] = []
    if (!dryRun) {
      const updates: Record<string, any> = {}
      for (const r of rows) {
        if (!r.sku) continue
        updates[String(r.sku)] = {
          active: !!r.active,
          minPrice: isFiniteNumber(r.min) ? r.min : undefined,
          maxPrice: isFiniteNumber(r.max) ? r.max : undefined,
          stepKzt: isFiniteNumber(r.step) ? r.step : undefined,
        }
      }
      const st = upsertV2(String(storeId || ''), updates)
      Object.keys(updates).slice(0,5).forEach(sku=> changes.push({ sku, settings: st.sku[sku] }))
    }
    return NextResponse.json({ ok: true, dryRun, total: rows.length, applied: dryRun ? 0 : Object.keys(rows).length, sample: changes.slice(0, 5), storeId: storeId || undefined })
  } catch (e:any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}

function isFiniteNumber(v:any){ return typeof v === 'number' && Number.isFinite(v) }



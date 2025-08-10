import { NextResponse } from 'next/server'
import { getMerchantId, mcFetch } from '@/lib/kaspi/client'

function pickArrayKey(obj: any): { key: string | null; arr: any[] } {
  const candidates = [
    'items',
    'content',
    'data.items',
    'data.content',
    'data',
    'list',
    'offers',
    'results',
    'rows',
    'page.content',
  ]
  for (const key of candidates) {
    const parts = key.split('.')
    let cur: any = obj
    for (const p of parts) cur = cur?.[p]
    if (Array.isArray(cur)) return { key, arr: cur }
  }
  return { key: null, arr: [] }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const raw = searchParams.get('raw') === '1'
    const paramset = searchParams.get('paramset') || 'a'
    const m = getMerchantId()

    const urlA = `/bff/offer-view/list?m=${m}&p=0&l=50&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`
    const urlB = `/bff/offer-view/list?m=${m}&p=0&l=10&available=true&t=&c=&lowStock=false&notSpecifiedStock=false`
    const url = paramset === 'available' ? urlB : urlA
    const res = await mcFetch(url)
    const text = await res.text()
    let json: any
    try { json = JSON.parse(text) } catch { json = text }

    if (raw) return NextResponse.json(json)

    const picked = pickArrayKey(json)
    return NextResponse.json({ ok: true, pickedKey: picked.key, length: picked.arr.length })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}



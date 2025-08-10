import { NextResponse } from 'next/server'
import { mcFetch, getMerchantId } from '@/lib/kaspi/client'
import { readCookieFromStore } from '@/lib/kaspi/cookieStore'

export const dynamic = 'force-dynamic'
export async function GET() {
  try {
    // Surface which auth path we have for easier troubleshooting
    const cookiePresent = !!(process.env.KASPI_MERCHANT_COOKIE || process.env.KASPI_MERCHANT_COOKIES || readCookieFromStore())
    const keyPresent = !!process.env.KASPI_MERCHANT_API_KEY
    const m = getMerchantId()
    const res = await mcFetch(`/offers/api/v1/offer/count?m=${m}`)
    const data = await res.json()
    return NextResponse.json({ ok: true, status: 200, data, auth: { cookiePresent, keyPresent, mode: process.env.KASPI_MERCHANT_AUTH_MODE || 'cookie' } })
  } catch (e:any) {
    const msg = (e && e.message) || 'unknown'
    const status = msg.includes('401') ? 401 : 500
    return NextResponse.json({ ok: false, status, error: msg, auth: { mode: process.env.KASPI_MERCHANT_AUTH_MODE || 'cookie' } }, { status })
  }
}
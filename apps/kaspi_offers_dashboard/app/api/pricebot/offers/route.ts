import { NextResponse } from 'next/server';
import { getOffersPage } from '@/lib/merchant/client';
export const runtime = 'nodejs';

export async function GET() {
  try {
    if (!process.env.KASPI_MERCHANT_API_BASE || !process.env.KASPI_MERCHANT_ID) {
      return NextResponse.json({ error:'MISSING_ENV' }, { status:500 });
    }

    // page through the list
    let page = 0, limit = 100, all: any[] = [];
    // cap to avoid infinite loops
    for (; page < 20; page++) {
      const js = await getOffersPage(page, limit) as any
      const items = Array.isArray(js?.items) ? js.items : []
      all = all.concat(items)
      if (!items.length || items.length < limit) break
    }

    const offers = all.map((o:any) => ({
      name: o.name || o.title || o.productName || '',
      // prefer numeric if present, else use SKU `s`
      variantProductId: String(o.variantProductId ?? o.productId ?? o.id ?? o.s ?? ''),
      sku: o.s || null,
      ourPrice: Number(o.price ?? o.currentPrice ?? o.offerPrice ?? 0),
      stock: Number(o.stock ?? o.qty ?? o.available ?? 0),
    }));

    if (!offers.length) return NextResponse.json({ error:'NO_DATA', offers:[] }, { status:200 });
    return NextResponse.json({ offers }, { status:200 });

  } catch (e:any) {
    const msg = String(e?.message || '');
    const code = /MISSING_COOKIE/.test(msg) ? 'MISSING_COOKIE'
               : /401|403/.test(msg) ? 'AUTH_FAILED'
               : /404/.test(msg) ? 'BAD_API_BASE'
               : 'MERCHANT_ERR';
    return NextResponse.json({ error: code, detail: msg.slice(0,300) }, { status:502 });
  }
}
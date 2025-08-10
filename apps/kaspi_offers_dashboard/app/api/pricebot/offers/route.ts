import { NextResponse } from 'next/server';
import { getMerchantId, mcFetch } from '@/lib/kaspi/client';
import { getSettings } from '@/lib/pricebot/storage';
export const runtime = 'nodejs';

export async function GET() {
  try {
    if (!process.env.KASPI_MERCHANT_API_BASE || !process.env.KASPI_MERCHANT_ID) {
      return NextResponse.json({ error:'MISSING_ENV' }, { status:500 });
    }

    // page through the list
    let page = 0; const limit = 100; let all: any[] = [];
    // cap to avoid infinite loops
    for (; page < 20; page++) {
      const m = getMerchantId();
      const url = `/bff/offer-view/list?m=${m}&p=${page}&l=${limit}&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`;
      const res = await mcFetch(url);
      const js = await res.json() as any;
      const items = Array.isArray(js?.items) ? js.items : [];
      all = all.concat(items);
      if (!items.length || items.length < limit) break;
    }

    const offers = all.map((o:any) => {
      const sku = o.merchantSku || o.sku || o.offerSku || o.id || ''
      const settings = sku ? getSettings(sku) : undefined
      return {
        name: o.name || o.title || o.productName || '',
        sku: sku || null,
        productId: Number(o.variantProductId ?? o.productId ?? o.id ?? 0),
        price: Number(o.price ?? o.currentPrice ?? o.offerPrice ?? 0),
        opponents: Number(o.sellersCount || o.opponents || 0),
        settings,
      }
    });

    if (!offers.length) return NextResponse.json({ ok:true, items:[] }, { status:200 });
    return NextResponse.json({ ok:true, items: offers }, { status:200 });

  } catch (e:any) {
    const msg = String(e?.message || '');
    const code = /MISSING_COOKIE/.test(msg) ? 'MISSING_COOKIE'
               : /401|403/.test(msg) ? 'AUTH_FAILED'
               : /404/.test(msg) ? 'BAD_API_BASE'
               : 'MERCHANT_ERR';
    return NextResponse.json({ error: code, detail: msg.slice(0,300) }, { status:502 });
  }
}
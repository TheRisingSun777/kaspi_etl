import { NextResponse } from 'next/server';
import { updatePriceBySku } from '@/server/merchant/client';

export const runtime = 'nodejs';

export async function POST(req: Request) {
  try {
    const { sku, price, cityId } = await req.json();
    if (!sku || typeof price !== 'number') {
      return NextResponse.json(
        { ok: false, error: 'BAD_INPUT', hint: 'Body must include { sku: string, price: number, cityId?: string }' },
        { status: 400 },
      );
    }
    const result = await updatePriceBySku({ sku, newPrice: price, cityId });
    return NextResponse.json({ ok: true, result });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e.message || e) }, { status: 500 });
  }
}
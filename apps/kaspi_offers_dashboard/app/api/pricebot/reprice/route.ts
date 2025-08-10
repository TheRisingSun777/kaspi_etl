import { NextResponse } from 'next/server';
import { updatePriceBySku } from '@/server/merchant/client';
import { getItemSettingsOrDefault } from '@/server/db/pricebot.store'

export const runtime = 'nodejs';

export async function POST(req: Request) {
  try {
    const { sku, price, cityId, useSettings } = await req.json();
    if (!sku) {
      return NextResponse.json(
        { ok: false, error: 'BAD_INPUT', hint: 'Body must include { sku: string, price?: number, cityId?: string, useSettings?: boolean }' },
        { status: 400 },
      );
    }
    const targetPrice = typeof price === 'number' ? price : (useSettings ? getItemSettingsOrDefault(sku).min : undefined)
    if (typeof targetPrice !== 'number' || !Number.isFinite(targetPrice)) {
      return NextResponse.json({ ok: false, error: 'MISSING_PRICE' }, { status: 400 })
    }
    const result = await updatePriceBySku({ sku, newPrice: targetPrice, cityId });
    return NextResponse.json({ ok: true, result });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e.message || e) }, { status: 500 });
  }
}
'use client';

import {useEffect, useState} from 'react';

type OfferRow = {
  sku: string;
  name?: string;
  productId?: number | null;
  price: number | null;
  stock?: number | null;
  opponents?: number | null;
};

function pickItems(json: any): OfferRow[] {
  if (Array.isArray(json?.items)) return json.items;
  if (Array.isArray(json?.result)) return json.result;
  if (Array.isArray(json?.data?.items)) return json.data.items;
  if (Array.isArray(json?.data)) return json.data;
  return [];
}

export default function PricebotTable() {
  const [rows, setRows] = useState<OfferRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch('/api/pricebot/offers?withOpponents=false', { cache: 'no-store' });
      const json = await res.json();
      setRows(pickItems(json));
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load');
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="overflow-x-auto">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-gray-500">Pricebot (live offers)</div>
        <button className="btn-outline" onClick={load}>Reload</button>
      </div>

      {loading && <div className="text-sm text-gray-500">Loading…</div>}
      {error && <div className="text-sm text-red-500">Error: {error}</div>}

      <table className="min-w-full text-sm">
        <thead className="text-left text-gray-500">
          <tr>
            <th className="p-2">Name</th>
            <th className="p-2">SKU</th>
            <th className="p-2">Variant</th>
            <th className="p-2">Our Price</th>
            <th className="p-2">Stock</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const variant = r.sku.match(/\(([^)]+)\)\s*$/)?.[1] ?? '';
            const name = r.name || r.sku.split('_').slice(0, 3).join(' ');
            return (
              <tr key={r.sku} className="border-t border-border">
                <td className="p-2">{name}</td>
                <td className="p-2 font-mono">{r.sku}</td>
                <td className="p-2">{variant}</td>
                <td className="p-2">{r.price ?? ''}</td>
                <td className="p-2">{r.stock ?? ''}</td>
              </tr>
            );
          })}

          {rows.length === 0 && !loading && !error && (
            <tr>
              <td colSpan={5} className="p-2 text-sm text-gray-500">
                No offers returned. Check /api/debug/merchant and credentials in .env.local.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
'use client';

import {useEffect, useMemo, useState} from 'react';
import { useReactTable, getCoreRowModel, getSortedRowModel, getFilteredRowModel, flexRender, createColumnHelper } from '@tanstack/react-table'

type OfferRow = {
  sku: string;
  name?: string;
  productId?: number | null;
  price: number | null;
  stock?: number | null;
  opponents?: number | null;
  settings?: { active: boolean; min: number; max: number; step: number; intervalMinutes: number; ignoreSellers: string[] }
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

  // Simple filter state
  const [filter, setFilter] = useState('')
  const columnHelper = createColumnHelper<OfferRow>()
  const columns = useMemo(()=>[
    columnHelper.accessor('name', { header: 'Name', cell: info => info.getValue() || '' }),
    columnHelper.accessor('sku', { header: 'SKU', cell: info => <a className="underline" href={`https://mc.shop.kaspi.kz/merchantcabinet/offers?search=${encodeURIComponent(info.getValue()||'')}`} target="_blank" rel="noreferrer">{info.getValue()}</a> }),
    columnHelper.accessor('productId', { header: 'Variant', cell: info => String(info.getValue()||'') }),
    columnHelper.accessor('price', { header: 'Our Price', cell: info => info.getValue() ?? '' }),
    columnHelper.accessor('stock', { header: 'Stock', cell: info => info.getValue() ?? '' }),
  ],[])
  const table = useReactTable({ data: rows, columns, state: { globalFilter: filter }, onGlobalFilterChange: setFilter, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getFilteredRowModel: getFilteredRowModel() })

  return (
    <div className="overflow-x-auto">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-gray-500">Pricebot (live offers)</div>
        <div className="flex items-center gap-2">
          <input className="input" placeholder="Filter by text…" value={filter} onChange={e=>setFilter(e.target.value)} />
          <a className="btn-outline" href="/api/pricebot/export?format=csv">Download CSV</a>
          <a className="btn-outline" href="/api/pricebot/export?format=xlsx">Download XLSX</a>
          <button className="btn-outline" onClick={load}>Reload</button>
        </div>
      </div>

      {loading && <div className="text-sm text-gray-500">Loading…</div>}
      {error && <div className="text-sm text-red-500">Error: {error}</div>}

      <table className="min-w-full text-sm">
        <thead className="text-left text-gray-500">
          {table.getHeaderGroups().map(hg=> (
            <tr key={hg.id}>
              {hg.headers.map(h=>(
                <th key={h.id} className="p-2 cursor-pointer" onClick={h.column.getToggleSortingHandler()}>
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr key={row.id} className="border-t border-border">
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="p-2">{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          ))}

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
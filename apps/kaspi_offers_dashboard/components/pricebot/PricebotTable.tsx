'use client';

import {useEffect, useMemo, useRef, useState} from 'react';
import { useReactTable, getCoreRowModel, getSortedRowModel, getFilteredRowModel, flexRender, createColumnHelper } from '@tanstack/react-table'
import OpponentsModal from './OpponentsModal'

type OfferRow = {
  sku: string;
  name?: string;
  productId?: number | null;
  price: number | null;
  stock?: number | null;
  opponents?: number | null;
  settings?: { active: boolean; min: number; max: number; step: number; interval: number; ignoreSellers: string[] }
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
  const saveQueue = useRef<ReturnType<typeof setTimeout>|null>(null)

  function debouncedSave(sku: string, patch: any) {
    if (saveQueue.current) clearTimeout(saveQueue.current)
    saveQueue.current = setTimeout(async ()=>{
      await fetch('/api/pricebot/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ items: { [sku]: patch } }) })
      await load()
    }, 500)
  }

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
  const [showOpp, setShowOpp] = useState<{sku:string, productId:number|null}|null>(null)
  const columns = useMemo(()=>[
    columnHelper.accessor(row=>row.settings?.active??false, { id:'active', header: 'Active', cell: info => {
      const r = info.row.original
      const val = !!(r.settings?.active)
      return <input type="checkbox" defaultChecked={val} onChange={e=>debouncedSave(r.sku, { active: e.currentTarget.checked })} />
    }}),
    columnHelper.accessor('name', { header: 'Name', cell: info => info.getValue() || '' }),
    columnHelper.accessor('sku', { header: 'SKU', cell: info => {
      const sku = info.getValue()||''
      const pid = info.row.original.productId
      const link = pid ? `https://kaspi.kz/shop/p/-${pid}/?c=${process.env.NEXT_PUBLIC_DEFAULT_CITY_ID||'710000000'}` : `https://kaspi.kz/shop/search/?text=${encodeURIComponent(sku)}`
      return <a className="underline font-mono" href={link} target="_blank" rel="noreferrer">{sku}</a>
    }}),
    columnHelper.accessor('productId', { header: 'Variant', cell: info => String(info.getValue()||'') }),
    columnHelper.accessor('price', { header: 'Our Price', cell: info => info.getValue() ?? '' }),
    columnHelper.accessor('stock', { header: 'Stock', cell: info => info.getValue() ?? '' }),
    columnHelper.accessor(row=>row.settings?.min ?? 0, { id:'min', header:'Min', cell: info => {
      const r = info.row.original; const def = r.settings?.min ?? 0
      return <input className="input w-24" defaultValue={def} onBlur={e=>debouncedSave(r.sku, { min: Number(e.currentTarget.value) })} />
    }}),
    columnHelper.accessor(row=>row.settings?.max ?? 0, { id:'max', header:'Max', cell: info => {
      const r = info.row.original; const def = r.settings?.max ?? 0
      return <input className="input w-24" defaultValue={def} onBlur={e=>debouncedSave(r.sku, { max: Number(e.currentTarget.value) })} />
    }}),
    columnHelper.accessor(row=>row.settings?.step ?? 1, { id:'step', header:'Step (KZT)', cell: info => {
      const r = info.row.original; const def = r.settings?.step ?? 1
      return <input className="input w-20" defaultValue={def} onBlur={e=>debouncedSave(r.sku, { step: Number(e.currentTarget.value) })} />
    }}),
    columnHelper.accessor(row=>row.settings?.interval ?? 5, { id:'interval', header:'Interval (min)', cell: info => {
      const r = info.row.original; const def = r.settings?.interval ?? 5
      return <input className="input w-20" defaultValue={def} onBlur={e=>debouncedSave(r.sku, { interval: Number(e.currentTarget.value) })} />
    }}),
    columnHelper.accessor(row=>row.opponents ?? 0, { id:'opponents', header:'Opponents', cell: info => {
      const r = info.row.original
      const n = Number(info.getValue()||0)
      return <button className="underline" onClick={()=>setShowOpp({ sku: r.sku, productId: (r.productId as any)||null })}>{n}</button>
    }}),
  ],[])
  const table = useReactTable({ data: rows, columns, state: { globalFilter: filter }, onGlobalFilterChange: setFilter, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getFilteredRowModel: getFilteredRowModel() })

  return (
    <>
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
    {showOpp && (
      <OpponentsModal
        sku={showOpp.sku}
        productId={showOpp.productId}
        cityId={String(process.env.NEXT_PUBLIC_DEFAULT_CITY_ID||'710000000')}
        initialIgnores={[]}
        onToggle={(id,ignore)=>{ debouncedSave(showOpp.sku, { ignoreSellers: [] }); }}
        onClose={()=>setShowOpp(null)}
      />
    )}
  </>
  );
}
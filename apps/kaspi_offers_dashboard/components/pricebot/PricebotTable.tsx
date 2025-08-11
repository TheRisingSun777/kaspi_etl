'use client';

import {useEffect, useMemo, useRef, useState} from 'react';
import { useReactTable, getCoreRowModel, getSortedRowModel, getFilteredRowModel, flexRender, createColumnHelper } from '@tanstack/react-table'
import OpponentsModal from './OpponentsModal'
import RunConfirmModal from './RunConfirmModal'

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

export default function PricebotTable({ storeId }: { storeId?: string }) {
  const [rows, setRows] = useState<OfferRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saveQueue = useRef<ReturnType<typeof setTimeout>|null>(null)

  function debouncedSave(sku: string, patch: any) {
    if (saveQueue.current) clearTimeout(saveQueue.current)
    saveQueue.current = setTimeout(async ()=>{
      await fetch('/api/pricebot/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ storeId, items: { [sku]: patch } }) })
      await load()
    }, 500)
  }

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const url = `/api/pricebot/offers?withOpponents=false${storeId?`&merchantId=${storeId}`:''}`
      const res = await fetch(url, { cache: 'no-store' });
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
  const [confirmRun, setConfirmRun] = useState<{ sku:string; ourPrice:number; target:number }|null>(null)
  const columns = useMemo(()=>[
    columnHelper.accessor(row=>row.settings?.active??false, { id:'active', header: 'Active', cell: info => {
      const r = info.row.original
      const val = !!(r.settings?.active)
      const isZero = Number(r.stock||0) <= 0
      return <input type="checkbox" defaultChecked={isZero ? false : val} disabled={isZero} title={isZero? 'Auto-disabled: zero stock':''} onChange={e=>debouncedSave(r.sku, { active: e.currentTarget.checked })} />
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
    columnHelper.display({ id:'actions', header:'Run', cell: info => {
      const r = info.row.original
      return <button className="btn-outline" onClick={async()=>{
        const resp = await fetch('/api/pricebot/run', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ storeId, sku: r.sku, ourPrice: r.price, dry: true }) })
        const js = await resp.json()
        const target = js?.proposal?.targetPrice ?? js?.proposal?.price
        if (typeof target === 'number') setConfirmRun({ sku: r.sku, ourPrice: Number(r.price||0), target })
      }}>Run</button>
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
          <a className="btn-outline" href={`/api/pricebot/export?format=csv${storeId?`&storeId=${storeId}`:''}`}>Download CSV</a>
          <a className="btn-outline" href={`/api/pricebot/export?format=xlsx${storeId?`&storeId=${storeId}`:''}`}>Download XLSX</a>
          <button className="btn-outline" onClick={async()=>{
            const res = await fetch('/api/pricebot/bulk', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ storeId }) })
            const js = await res.json(); if (js?.jobId) alert(`Bulk job started: ${js.jobId}`)
          }}>Bulk Run</button>
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
          {table.getRowModel().rows.map(row => {
            const isZero = Number((row.original as any).stock||0) <= 0
            return (
            <tr key={row.id} className={`border-t border-border ${isZero ? 'opacity-50' : ''}`}>
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="p-2">{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          )})}

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
        merchantId={storeId}
        onToggle={async (id,ignore)=>{ await fetch('/api/pricebot/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ merchantId: storeId, updates: { [showOpp.sku]: { ignoredOpponents: ignore ? [id] : [] } } }) }); await load() }}
        onClose={()=>setShowOpp(null)}
      />
    )}
    {confirmRun && (
      <RunConfirmModal
        sku={confirmRun.sku}
        ourPrice={confirmRun.ourPrice}
        targetPrice={confirmRun.target}
        onApply={async()=>{ await fetch('/api/pricebot/run', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ storeId, sku: confirmRun.sku, ourPrice: confirmRun.ourPrice, dry: false }) }); setConfirmRun(null); await load() }}
        onClose={()=>setConfirmRun(null)}
      />
    )}
  </>
  );
}
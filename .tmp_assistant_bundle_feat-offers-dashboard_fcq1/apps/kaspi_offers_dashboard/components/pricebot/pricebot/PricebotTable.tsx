'use client';

import {useEffect, useMemo, useRef, useState} from 'react';
import { usePricebotStore } from '@/lib/pricebot/store'
import { enrichRow } from '@/lib/pricebot/enrich'
import { useReactTable, getCoreRowModel, getSortedRowModel, getFilteredRowModel, flexRender, createColumnHelper } from '@tanstack/react-table'
import OpponentsModal from './OpponentsModal'
import RunConfirmModal from './RunConfirmModal'
import BulkProgress from './BulkProgress'

type OfferRow = {
  sku: string;
  name?: string;
  productId?: number | null;
  price: number | null;
  stock?: number | null;
  opponents?: number | null;
  settings?: { active: boolean; min: number; max: number; step: number; interval: number; ignoreSellers: string[] }
};

// legacy helper retained for reference

export default function PricebotTable({ storeId }: { storeId?: string }) {
  const rows = usePricebotStore(s=>s.rows) as any as OfferRow[]
  const storeCity = String(process.env.NEXT_PUBLIC_DEFAULT_CITY_ID||'710000000')
  const loading = usePricebotStore(s=>s.loading)
  const error = usePricebotStore(s=>s.error)
  const saveQueue = useRef<ReturnType<typeof setTimeout>|null>(null)

  function debouncedSave(sku: string, patch: any) {
    if (saveQueue.current) clearTimeout(saveQueue.current)
    saveQueue.current = setTimeout(async ()=>{
      await fetch('/api/pricebot/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ storeId, items: { [sku]: patch } }) })
      await load()
    }, 500)
  }

  async function load() { usePricebotStore.getState().loadOffers(storeId) }
  useEffect(() => { load(); }, [storeId]);

  // Simple filter state
  const [filter, setFilter] = useState('')
  const columnHelper = createColumnHelper<OfferRow>()
  const [showOpp, setShowOpp] = useState<{sku:string, productId:number|null}|null>(null)
  const [confirmRun, setConfirmRun] = useState<{ sku:string; ourPrice:number; target:number }|null>(null)
  const [bulkJob, setBulkJob] = useState<string|undefined>()
  const columns = useMemo(()=>[
    columnHelper.accessor(row=>row.settings?.active??false, { id:'active', header: 'Active', cell: info => {
      const r = info.row.original
      const val = !!(r.settings?.active)
      const isZero = Number(r.stock||0) <= 0
      return <input type="checkbox" defaultChecked={isZero ? false : val} disabled={isZero} title={isZero? 'Auto-disabled: zero stock':''} onChange={e=>debouncedSave(r.sku, { active: e.currentTarget.checked })} />
    }}),
    columnHelper.accessor('name', { header: 'Name', cell: info => {
      const name = info.getValue() || ''
      const r = info.row.original
      const n = Number(r.opponents||0)
      return (
        <div className="flex items-center gap-2">
          <span>{name}</span>
          <button className="text-xs underline" title="Show sellers" onClick={()=>setShowOpp({ sku: r.sku, productId: (r.productId as any)||null })}>{n}</button>
          <button className="text-xs text-blue-400" title="Enrich" onClick={async()=>{ const e = await enrichRow(r as any, { cityId: storeCity }); usePricebotStore.getState().patchRow(String(r.productId||r.sku||''), e as any) }}>↻</button>
        </div>
      )
    }}),
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
    columnHelper.accessor(row=>row.opponents ?? 0, { id:'opponents', header:'Sellers', cell: info => {
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
            const js = await res.json(); if (js?.jobId) setBulkJob(js.jobId)
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

          {table.getRowModel().rows.length === 0 && !loading && !error && (
            <tr>
              {/*  make the cell span exactly the number of visible columns  */}
              <td colSpan={table.getAllLeafColumns().length} className="p-2 text-sm text-gray-500">
              No products match the current filter. Reload or adjust your filters to see data.
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
    {bulkJob && (
      <BulkProgress jobId={bulkJob} onClose={()=>setBulkJob(undefined)} />
    )}
  </>
  );
}
"use client"
import { useEffect, useState } from 'react'

type Row = {
  name: string
  variantProductId: string
  ourPrice: number
  rules: { minPrice: number; maxPrice: number; step: number; intervalMin: number; active: number } | null
  opponentCount: number
}

export default function PricebotPanel() {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true); setError(null)
    try {
      const res = await fetch('/api/pricebot/offers', { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setRows(Array.isArray(json.rows) ? json.rows : [])
    } catch (e:any) { setError(e?.message||'Failed') }
    finally { setLoading(false) }
  }

  useEffect(()=>{ load() }, [])

  const saveRule = async (id: string, body: any) => {
    await fetch(`/api/pricebot/rules/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    await load()
  }

  const reprice = async (id: string) => {
    const res = await fetch(`/api/pricebot/reprice/${id}`, { method: 'POST' })
    if (res.ok) await load()
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-gray-500">Pricebot (Store {process.env.NEXT_PUBLIC_KASPI_MERCHANT_ID || '30141222'})</div>
        <div className="flex gap-2">
          <button className="btn-outline" onClick={load} disabled={loading}>{loading ? 'Loading…' : 'Reload'}</button>
          <button className="btn-outline" onClick={async ()=>{ await fetch('/api/pricebot/reprice-bulk', { method:'POST' }); }}>
            Run All (bulk)
          </button>
        </div>
      </div>
      {error && <div className="text-red-500 text-sm mb-2">{error}</div>}
      <div className="overflow-x-auto min-h-[120px]">
        {(!rows || rows.length===0) && !loading && !error && (
          <div className="text-sm text-gray-500 p-2">No offers found. Add credentials to .env.local or provide server/db/seed.offers.json.</div>
        )}
        <table className="min-w-full text-sm">
          <thead className="text-left text-gray-500">
            <tr>
              <th className="p-2">Name</th>
              <th className="p-2">Variant ID</th>
              <th className="p-2">Our Price</th>
              <th className="p-2">Min</th>
              <th className="p-2">Max</th>
              <th className="p-2">Step</th>
              <th className="p-2">Interval</th>
              <th className="p-2">Active</th>
              <th className="p-2">Run</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r)=>{
              const rule = r.rules || { minPrice: r.ourPrice, maxPrice: r.ourPrice, step: 1, intervalMin: 5, active: 0 }
              return (
                <tr key={r.variantProductId} className="border-t border-border">
                  <td className="p-2">{r.name}</td>
                  <td className="p-2 text-gray-500">{r.variantProductId}</td>
                  <td className="p-2">{new Intl.NumberFormat('ru-KZ').format(r.ourPrice)}</td>
                  <td className="p-2"><input className="input w-24" defaultValue={rule.minPrice} onBlur={e=>rule.minPrice=Number(e.currentTarget.value)} /></td>
                  <td className="p-2"><input className="input w-24" defaultValue={rule.maxPrice} onBlur={e=>rule.maxPrice=Number(e.currentTarget.value)} /></td>
                  <td className="p-2"><input className="input w-20" defaultValue={rule.step} onBlur={e=>rule.step=Number(e.currentTarget.value)} /></td>
                  <td className="p-2"><input className="input w-20" defaultValue={rule.intervalMin} onBlur={e=>rule.intervalMin=Number(e.currentTarget.value)} /></td>
                  <td className="p-2"><input type="checkbox" defaultChecked={!!rule.active} onChange={e=>rule.active = e.currentTarget.checked?1:0} /></td>
                  <td className="p-2 flex gap-2">
                    <button className="btn-outline" onClick={()=>saveRule(r.variantProductId, rule)}>Save</button>
                    <button className="btn-outline" onClick={()=>reprice(r.variantProductId)}>Run</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}



"use client"
import { useEffect, useState } from 'react'

type Offer = { name: string; sku: string|null; variantProductId: string; ourPrice: number; stock: number }

export default function PricebotTable() {
  const [rows, setRows] = useState<Offer[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string|null>(null)

  const load = async () => {
    setLoading(true); setError(null)
    try {
      const res = await fetch('/api/pricebot/offers?withOpponents=false', { cache: 'no-store' })
      const js = await res.json()
      if (!res.ok) throw new Error(js?.error || `HTTP ${res.status}`)
      setRows(js.offers || [])
    } catch (e:any) { setError(String(e?.message||e)) }
    finally { setLoading(false) }
  }

  useEffect(()=>{ load() }, [])

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-gray-500">Pricebot (live offers)</div>
        <button className="btn-outline" onClick={load} disabled={loading}>{loading?'Loading…':'Reload'}</button>
      </div>
      {error && <div className="text-sm text-red-500">{error}</div>}
      {!error && rows.length===0 && !loading && (
        <div className="text-sm text-gray-500">No offers returned. Check /api/debug/merchant and credentials in .env.local.</div>
      )}
      <div className="overflow-x-auto">
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
            {rows.map((r,i)=> (
              <tr key={i} className="border-t border-border">
                <td className="p-2">{r.name}</td>
                <td className="p-2 text-gray-500">{r.sku||'—'}</td>
                <td className="p-2 text-gray-500">{r.variantProductId}</td>
                <td className="p-2">{new Intl.NumberFormat('ru-KZ').format(r.ourPrice)}</td>
                <td className="p-2">{r.stock}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}



"use client"
import { useEffect, useState } from 'react'

type Row = {
  name: string
  variantProductId: string
  ourPrice: number
  rules: { minPrice: number; maxPrice: number; step: number; intervalMin: number; active: number } | null
  opponentCount: number
}

export default function PricebotPanel({ storeId }: { storeId?: string }) {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [base, setBase] = useState('')
  const [merchantId, setMerchantId] = useState('')

  const load = async () => {
    setLoading(true); setError(null)
    try {
      // load settings first
      try {
        const sres = await fetch(`/api/pricebot/settings${storeId?`?storeId=${storeId}`:''}`)
        if (sres.ok) {
          const js = await sres.json()
          if (js?.settings?.base) setBase(js.settings.base)
          if (js?.settings?.merchantId) setMerchantId(js.settings.merchantId)
        }
      } catch {}
      const res = await fetch(`/api/pricebot/offers${storeId?`?storeId=${storeId}`:''}`, { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setRows(Array.isArray(json.items) ? json.items.map((it:any)=>({
        name: it.name,
        variantProductId: String(it.productId || ''),
        ourPrice: Number(it.price || 0),
        rules: null,
        opponentCount: Number(it.opponents || 0),
      })) : [])
      if ((!json.items || json.items.length===0) && json.debug) {
        console.log('[pricebot-debug]', ...json.debug)
      }
    } catch (e:any) { setError(e?.message||'Failed') }
    finally { setLoading(false) }
  }

  useEffect(()=>{ load() }, [storeId])

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
        <div className="flex gap-2 items-end">
          <div>
            <label className="block text-xs text-gray-500">API Base</label>
            <input className="input w-[280px]" value={base} onChange={e=>setBase(e.target.value)} placeholder="https://kaspi.kz/shop/api/v2" />
          </div>
          <div>
            <label className="block text-xs text-gray-500">Merchant ID</label>
            <input className="input w-[160px]" value={merchantId} onChange={e=>setMerchantId(e.target.value)} placeholder="30141222" />
          </div>
          <button className="btn-outline" onClick={async()=>{ await fetch('/api/pricebot/settings', { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ base, merchantId }) }); await load() }}>
            Save Settings
          </button>
          <button className="btn-outline" onClick={load} disabled={loading}>{loading ? 'Loading…' : 'Reload'}</button>
          <button className="btn-outline" onClick={async ()=>{ await fetch('/api/pricebot/reprice-bulk', { method:'POST' }); }}>
            Run All (bulk)
          </button>
        </div>
      </div>
      {error && <div className="text-red-500 text-sm mb-2">{error}</div>}
      <div className="overflow-x-auto min-h-[120px]">
        {(!rows || rows.length===0) && !loading && !error && (
          <div className="text-sm text-gray-500 p-2">No offers returned. Debug: see <a className="underline" href="/api/debug/merchant/list?raw=1" target="_blank">/api/debug/merchant/list?raw=1</a></div>
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



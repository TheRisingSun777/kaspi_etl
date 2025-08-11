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
  const [stats, setStats] = useState<any>(null)
  const [statsLoading, setStatsLoading] = useState(false)

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

  useEffect(()=>{
    const loadStats = async()=>{
      setStatsLoading(true)
      try {
        const res = await fetch(`/api/pricebot/stats${storeId?`?storeId=${storeId}`:''}`, { cache: 'no-store' })
        const js = await res.json().catch(()=>null)
        setStats(js?.stats || null)
      } finally { setStatsLoading(false) }
    }
    loadStats()
  }, [storeId])

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
      <div className="grid sm:grid-cols-2 lg:grid-cols-6 gap-3 mb-4">
        <div className="card p-3"><div className="text-xs text-gray-500">Total SKUs</div><div className="text-xl font-semibold">{statsLoading? '…' : (stats?.totalSKUs ?? '—')}</div></div>
        <div className="card p-3"><div className="text-xs text-gray-500">Active SKUs</div><div className="text-xl font-semibold">{statsLoading? '…' : (stats?.activeSKUs ?? '—')}</div></div>
        <div className="card p-3"><div className="text-xs text-gray-500">Zero Stock</div><div className="text-xl font-semibold">{statsLoading? '…' : (stats?.zeroStock ?? '—')}</div></div>
        <div className="card p-3"><div className="text-xs text-gray-500">Competing</div><div className="text-xl font-semibold">{statsLoading? '…' : (stats?.competingSKUs ?? '—')}</div></div>
        <div className="card p-3"><div className="text-xs text-gray-500">Win Rate</div><div className="text-xl font-semibold">{statsLoading? '…' : (typeof stats?.winRate === 'number' ? `${Math.round(stats.winRate*100)}%` : '—')}</div></div>
        <div className="card p-3"><div className="text-xs text-gray-500">Last Run Δ</div><div className="text-xl font-semibold">{statsLoading? '…' : (stats?.lastRunAvgDelta ?? '—')}</div></div>
      </div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-gray-500">Pricebot (Store {storeId || process.env.NEXT_PUBLIC_KASPI_MERCHANT_ID || '30141222'})</div>
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
    </div>
  )
}



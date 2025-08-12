'use client'
import { useEffect, useState } from 'react'

export default function OpponentsModal({ productId, cityId, onClose, sku, initialIgnores, onToggle, merchantId }: { productId: number | null | undefined; cityId: string; sku: string; merchantId?: string; initialIgnores: string[]; onToggle: (_sellerId: string, _ignore: boolean)=>void; onClose: ()=>void }) {
  const [sellers, setSellers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string>('')

  useEffect(()=>{
    if (!productId) return
    const load = async () => {
      setLoading(true); setError(null);
      try {
        const params = new URLSearchParams({ sku, cityId: cityId || '710000000' });
        if (merchantId) params.set('merchantId', String(merchantId));
        if (productId)  params.set('productId', String(productId));
        const res = await fetch(`/api/pricebot/opponents?${params.toString()}`);
        const js  = await res.json();
        const list = Array.isArray(js?.items) ? js.items : [];
        list.sort((a: any, b: any) => Number(a.price || 0) - Number(b.price || 0));
        setSellers(list);
      } catch (e: any) {
        setError(e?.message || 'Failed');
      } finally {
        setLoading(false);
      }
    };
    load()
  }, [productId, cityId, sku, merchantId])

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg shadow-xl w-full max-w-2xl p-4 animate-in fade-in zoom-in">
        <div className="flex items-center justify-between mb-2">
          <div className="font-semibold">Opponents — {sku}</div>
          <button className="btn-outline" onClick={onClose}>Close</button>
        </div>
        {saved && <div className="text-xs text-green-500 mb-2">{saved}</div>}
        {loading && <div className="text-sm text-gray-400">Loading…</div>}
        {error && <div className="text-sm text-red-500">{error}</div>}
        <div className="max-h-[60vh] overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-gray-400">
              <tr>
                <th className="p-2">Seller</th>
                <th className="p-2">Price</th>
                <th className="p-2">Ignore</th>
              </tr>
            </thead>
            <tbody>
              {sellers.map((s:any)=>{
                const id = String(s.merchantId || s.merchantUID || s.id || '')
                const ignored = initialIgnores.includes(id)
                return (
                  <tr key={id} className="border-t border-border">
                    <td className="p-2">
                      {s.name || s.merchantName}
                      {ignored && <span className="ml-2 px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-[10px] align-middle">Ignored</span>}
                      {s.isYou && <span className="ml-2 px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[10px] align-middle">You</span>}
                    </td>
                    <td className="p-2">{s.price}</td>
                    <td className="p-2"><input type="checkbox" defaultChecked={ignored} onChange={(e)=>{ onToggle(id, e.currentTarget.checked); setSaved('Saved'); setTimeout(()=>setSaved(''), 700) }} /></td>
                  </tr>
                )
              })}
              {(!sellers || sellers.length===0) && !loading && (
                <tr><td colSpan={3} className="p-2 text-gray-500">No sellers</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}



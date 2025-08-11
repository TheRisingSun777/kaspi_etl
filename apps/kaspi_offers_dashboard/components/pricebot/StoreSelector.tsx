'use client'
import { useEffect, useState } from 'react'

export default function StoreSelector({ onChange }: { onChange: (id: string)=>void }) {
  const [stores, setStores] = useState<{id:string; name:string}[]>([])
  const [cur, setCur] = useState('')
  useEffect(()=>{ (async()=>{ const res = await fetch('/api/pricebot/stores', { cache:'no-store' }); const js = await res.json(); setStores(js.items||[]); const saved = typeof localStorage!=='undefined'? localStorage.getItem('pricebot.storeId') : null; setCur(saved || (js.items?.[0]?.id)||'') })() },[])
  useEffect(()=>{ 
    if (!cur) return
    try { localStorage.setItem('pricebot.storeId', cur) } catch {}
    onChange(cur)
    ;(async()=>{ try { await fetch('/api/debug/state', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ storeId: cur }) }) } catch {} })()
  }, [cur])
  return (
    <select className="input" value={cur} onChange={e=>setCur(e.target.value)}>
      {stores.map(s=> <option key={s.id} value={s.id}>{s.name} ({s.id})</option>)}
    </select>
  )
}



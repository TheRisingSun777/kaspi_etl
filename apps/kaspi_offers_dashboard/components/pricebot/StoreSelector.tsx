'use client'
import { useEffect, useState } from 'react'

export default function StoreSelector({ onChange }: { onChange: (id: string)=>void }) {
  const [stores, setStores] = useState<{id:string; name:string}[]>([])
  const [cur, setCur] = useState('')
  useEffect(()=>{ (async()=>{ const res = await fetch('/api/pricebot/stores'); const js = await res.json(); setStores(js.items||[]); setCur((js.items?.[0]?.id)||'') })() },[])
  useEffect(()=>{ if (cur) onChange(cur) }, [cur])
  return (
    <select className="input" value={cur} onChange={e=>setCur(e.target.value)}>
      {stores.map(s=> <option key={s.id} value={s.id}>{s.name} ({s.id})</option>)}
    </select>
  )
}



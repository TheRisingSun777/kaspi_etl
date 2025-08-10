'use client'
import { useEffect, useState } from 'react'

export default function GlobalIgnore() {
  const [list, setList] = useState<string[]>([])
  const [input, setInput] = useState('')

  async function load() {
    const res = await fetch('/api/pricebot/settings', { cache: 'no-store' })
    const js = await res.json()
    setList(js?.settings?.global?.ignoreSellers || [])
  }
  useEffect(()=>{ load() }, [])

  async function save(newList: string[]) {
    setList(newList)
    await fetch('/api/pricebot/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ global: { ignoreSellers: newList } }) })
  }

  function add() {
    const ids = input.split(/[\s,]+/).map(s=>s.trim()).filter(Boolean)
    if (!ids.length) return
    const set = new Set([ ...list, ...ids ])
    save(Array.from(set))
    setInput('')
  }

  function remove(id: string) {
    save(list.filter(x=>x!==id))
  }

  return (
    <div className="flex items-center gap-2">
      <input className="input" placeholder="Global ignore merchant IDs…" value={input} onChange={e=>setInput(e.target.value)} />
      <button className="btn-outline" onClick={add}>Add</button>
      <div className="flex flex-wrap gap-2">
        {list.map(id=> (
          <span key={id} className="px-2 py-1 rounded bg-gray-700/40 text-xs">
            {id} <button className="ml-1" onClick={()=>remove(id)}>×</button>
          </span>
        ))}
      </div>
    </div>
  )
}



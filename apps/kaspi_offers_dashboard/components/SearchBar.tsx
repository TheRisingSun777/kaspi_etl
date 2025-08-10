"use client"

import { useEffect, useMemo, useState } from 'react'

const DEFAULT_CITY_ID = process.env.NEXT_PUBLIC_DEFAULT_CITY_ID || '710000000'

interface Props {
  onAnalyze: (_masterProductId: string, _cityId: string) => void
  loading?: boolean
}

export default function SearchBar({ onAnalyze, loading }: Props) {
  const [productId, setProductId] = useState('')
  const [cityId, setCityId] = useState(DEFAULT_CITY_ID)
  const [history, setHistory] = useState<string[]>([])

  useEffect(() => {
    try {
      const raw = localStorage.getItem('recentProductIds')
      if (raw) setHistory(JSON.parse(raw))
    } catch {}
  }, [])

  const recent = useMemo(() => history.slice(0, 5), [history])

  const pushHistory = (id: string) => {
    const next = [id, ...history.filter((x) => x !== id)].slice(0, 5)
    setHistory(next)
    try {
      localStorage.setItem('recentProductIds', JSON.stringify(next))
    } catch {}
  }

  const handleAnalyze = () => {
    const id = productId.trim()
    if (!id) return
    pushHistory(id)
    onAnalyze(id, cityId)
  }

  return (
    <div className="card p-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="flex-1">
          <label className="block text-sm mb-1">Master Product ID</label>
          <input
            className="input"
            placeholder="e.g. 108382478"
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
          />
        </div>
        <div className="sm:w-56">
          <label className="block text-sm mb-1">City</label>
          <select className="input" value={cityId} onChange={(e) => setCityId(e.target.value)}>
            <option value="710000000">Astana / Nur-Sultan</option>
            <option value="750000000">Almaty</option>
            <option value="620000000">Shymkent</option>
          </select>
        </div>
        <div className="sm:w-40 flex items-end">
          <button className="btn-primary w-full" onClick={handleAnalyze} disabled={loading}>
            {loading ? 'Analyzing…' : 'Analyze'}
          </button>
        </div>
      </div>

      {recent.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-gray-500 mb-1">Recent:</div>
          <div className="flex flex-wrap gap-2">
            {recent.map((id) => (
              <button
                key={id}
                className="btn-outline text-xs"
                onClick={() => {
                  setProductId(id)
                  onAnalyze(id, cityId)
                }}
              >
                {id}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}



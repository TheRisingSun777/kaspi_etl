'use client'
import { useRef, useState } from 'react'

export default function ImportExportBar({ storeId }: { storeId?: string }) {
  const inputRef = useRef<HTMLInputElement|null>(null)
  const [preview, setPreview] = useState<any[]>([])
  const [error, setError] = useState<string|undefined>()

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    setError(undefined)
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch('/api/pricebot/import?dryRun=true', { method:'POST', body: fd })
    const js = await res.json().catch(()=>({ ok:false }))
    if (!js?.ok) { setError(js?.error || 'Import failed'); return }
    setPreview(js.sample || [])
  }

  async function apply() {
    const file = inputRef.current?.files?.[0]
    if (!file) return
    const fd = new FormData(); fd.append('file', file)
    await fetch('/api/pricebot/import?dryRun=false', { method:'POST', body: fd })
    setPreview([])
  }

  return (
    <div className="flex items-center gap-2">
      <a className="btn-outline" href={`/api/pricebot/export?format=csv${storeId?`&storeId=${storeId}`:''}`}>Export CSV</a>
      <a className="btn-outline" href={`/api/pricebot/export?format=xlsx${storeId?`&storeId=${storeId}`:''}`}>Export XLSX</a>
      <input type="file" accept=".csv,.xlsx" ref={inputRef} onChange={onPick} className="hidden" />
      <button className="btn-outline" onClick={()=>inputRef.current?.click()}>Upload CSV/XLSX</button>
      {error && <span className="text-sm text-red-500">{error}</span>}
      {preview.length>0 && (
        <button className="btn-outline" onClick={apply}>Apply changes</button>
      )}
    </div>
  )
}



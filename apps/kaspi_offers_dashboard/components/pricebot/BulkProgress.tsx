'use client'
import { useEffect, useState } from 'react'

export default function BulkProgress({ jobId, onClose }:{ jobId:string; onClose:()=>void }){
  const [job, setJob] = useState<any>(null)
  const [err, setErr] = useState<string|undefined>()
  const [applying, setApplying] = useState(false)
  useEffect(()=>{
    let alive = true
    const tick = async()=>{
      try {
        const res = await fetch(`/api/pricebot/bulk?jobId=${jobId}`, { cache:'no-store' })
        const js = await res.json()
        if (!alive) return
        setJob(js?.job)
        if (!js?.job || js?.job?.status==='done' || js?.job?.status==='error') return
        setTimeout(tick, 800)
      } catch(e:any){ setErr(e?.message||'Failed') }
    }
    tick();
    return ()=>{ alive=false }
  }, [jobId])
  const pct = job?.total ? Math.round((job.processed / job.total) * 100) : 0
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg shadow-xl w-full max-w-md p-4 space-y-3">
        <div className="font-semibold">Bulk Run Progress</div>
        {err && <div className="text-sm text-red-500">{err}</div>}
        <div className="text-sm">Status: {job?.status || 'queued'}</div>
        <div className="w-full bg-gray-700/40 h-2 rounded"><div className="bg-blue-500 h-2 rounded" style={{ width: `${pct}%` }} /></div>
        <div className="text-xs text-gray-400">{job?.processed || 0}/{job?.total || 0} ({pct}%)</div>
        <div className="flex justify-end gap-2">
          {job?.status==='done' && <button className="btn" disabled={applying} onClick={async()=>{ setApplying(true); await fetch(`/api/pricebot/bulk/${jobId}/apply`, { method:'POST' }); setApplying(false) }}>Apply All</button>}
          <button className="btn-outline" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}



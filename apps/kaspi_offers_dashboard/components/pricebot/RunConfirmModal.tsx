'use client'
import { useState } from 'react'

export default function RunConfirmModal({ sku, ourPrice, targetPrice, onApply, onClose }:{ sku:string; ourPrice:number; targetPrice:number; onApply:()=>Promise<void>; onClose:()=>void }){
  const [busy, setBusy] = useState(false)
  const delta = Math.round(targetPrice - (ourPrice||0))
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg shadow-xl w-full max-w-md p-4 space-y-3">
        <div className="font-semibold">Apply new price?</div>
        <div className="text-sm text-gray-400">SKU: <span className="font-mono">{sku}</span></div>
        <div className="text-sm">Current: {ourPrice || '—'} → Target: <span className="font-semibold">{targetPrice}</span> ({delta>=0?'+':''}{delta})</div>
        <div className="flex gap-2 justify-end">
          <button className="btn-outline" disabled={busy} onClick={onClose}>Cancel</button>
          <button className="btn" disabled={busy} onClick={async()=>{ setBusy(true); await onApply().finally(()=>setBusy(false)) }}>Apply now</button>
        </div>
      </div>
    </div>
  )
}



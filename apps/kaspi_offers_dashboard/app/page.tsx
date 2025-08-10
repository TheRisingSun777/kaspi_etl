"use client"

import { useMemo, useState } from 'react'
import SearchBar from '@/components/SearchBar'
import KpiCards from '@/components/KpiCards'
import VariantCard from '@/components/VariantCard'
import ModelInfo from '@/components/ModelInfo'
import AnalyticsPanel from '@/components/AnalyticsPanel'
import PricebotPanel from '@/components/PricebotPanel'
import type { AnalyzeResult } from '@/lib/types'
import { exportCSV, exportXLSX } from '@/lib/export'

export default function Page() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<AnalyzeResult | null>(null)
  const [includeOOS, setIncludeOOS] = useState(true)

  const totals = useMemo(() => {
    if (!data) return { variants: 0, sellers: 0 }
    const variants = data.variants.length
    const sellerNames = new Set<string>()
    for (const v of data.variants) {
      for (const s of v.sellers || []) sellerNames.add(s.name)
    }
    return { variants, sellers: sellerNames.size }
  }, [data])

  const onAnalyze = async (masterProductId: string, cityId: string) => {
    setError(null)
    setLoading(true)
    setData(null)
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ masterProductId, cityId }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const json = (await res.json()) as AnalyzeResult
      setData(json)
    } catch (e: any) {
      setError(e?.message || 'Failed to analyze')
    } finally {
      setLoading(false)
    }
  }

  const handleCopyJSON = async () => {
    if (!data) return
    await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
  }

  const handleExportCSV = () => {
    if (!data) return
    const filtered = filterForExport(data, includeOOS)
    const csv = exportCSV(filtered)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `kaspi_offers_${data.masterProductId}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleExportXLSX = () => {
    if (!data) return
    const filtered = filterForExport(data, includeOOS)
    const arrayBuffer = exportXLSX(filtered)
    const blob = new Blob([arrayBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `kaspi_offers_${data.masterProductId}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <main className="min-h-screen max-w-7xl mx-auto p-4 md:p-6 space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl md:text-3xl font-bold">Kaspi Offers Insight</h1>
      </header>

      <SearchBar onAnalyze={onAnalyze} loading={loading} />

      {error && (
        <div className="card p-4 text-red-600 dark:text-red-400">{error}</div>
      )}

      {loading && (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-4 animate-pulse">
              <div className="h-4 w-24 bg-border rounded mb-2" />
              <div className="h-5 w-48 bg-border rounded mb-3" />
              <div className="h-24 w-full bg-border rounded" />
            </div>
          ))}
        </div>
      )}

      {data && data.variants && !loading && (
        <div className="space-y-4">
          <ModelInfo data={data} />
          <KpiCards data={data} />
          <AnalyticsPanel data={data} />
          <PricebotPanel />

          <div className="flex flex-wrap gap-2">
            <button className="btn-outline" onClick={handleCopyJSON}>Copy JSON</button>
            <button className="btn-outline" onClick={handleExportCSV}>Export CSV</button>
            <button className="btn-outline" onClick={handleExportXLSX}>Export XLSX</button>
            <label className="text-sm text-gray-500 inline-flex items-center gap-2 ml-2">
              <input type="checkbox" checked={includeOOS} onChange={e=>setIncludeOOS(e.target.checked)} />
              Include out-of-stock in export
            </label>
          </div>

          {data.variants.length === 0 ? (
            <div className="card p-6 text-center text-gray-500">
              No sellers were found. {process.env.NODE_ENV !== 'production' ? 'Check files under data_raw/kaspi_debug for captured HTML.' : ''}
            </div>
          ) : (
            <section className="grid gap-4 sm:grid-cols-2">
              {[...data.variants]
                .filter(v => includeOOS ? true : v.sellers.some(s => s.price > 0))
                .sort((a,b)=>{
                  const ca = (a.variantColor||'').localeCompare(b.variantColor||'')
                  if (ca !== 0) return ca
                  const num = (s:string)=>{ const m = s.match(/(\d{2,3})/); return m? parseInt(m[1],10): 0 }
                  return num(a.variantSize||a.label) - num(b.variantSize||b.label)
                })
                .map((v) => (
                <VariantCard key={v.productId} variant={v} />
              ))}
            </section>
          )}
        </div>
      )}

      {!data && !error && !loading && (
        <div className="card p-6 text-center text-gray-500">Enter a master product ID above to begin.</div>
      )}
    </main>
  )
}

function filterForExport(data: AnalyzeResult, includeOOS: boolean): AnalyzeResult {
  if (includeOOS) return data
  const clone: AnalyzeResult = {
    ...data,
    variants: data.variants.map(v => ({
      ...v,
      sellers: v.sellers.filter(s => !(s.name === 'Out of stock' && s.price === 0))
    }))
  }
  return clone
}



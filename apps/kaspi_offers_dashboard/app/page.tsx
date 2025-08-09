"use client"

import { useMemo, useState } from 'react'
import SearchBar from '@/components/SearchBar'
import KpiCards from '@/components/KpiCards'
import VariantCard from '@/components/VariantCard'
import type { AnalyzeResult } from '@/lib/types'
import { exportCSV, exportXLSX } from '@/lib/export'

export default function Page() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<AnalyzeResult | null>(null)

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
    const csv = exportCSV(data)
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
    const arrayBuffer = exportXLSX(data)
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

      {data && data.variants && (
        <div className="space-y-4">
          <KpiCards data={data} />

          <div className="flex flex-wrap gap-2">
            <button className="btn-outline" onClick={handleCopyJSON}>Copy JSON</button>
            <button className="btn-outline" onClick={handleExportCSV}>Export CSV</button>
            <button className="btn-outline" onClick={handleExportXLSX}>Export XLSX</button>
          </div>

          {data.variants.length === 0 ? (
            <div className="card p-6 text-center text-gray-500">
              No sellers were found. {process.env.NODE_ENV !== 'production' ? 'Check files under data_raw/kaspi_debug for captured HTML.' : ''}
            </div>
          ) : (
            <section className="grid gap-4 sm:grid-cols-2">
              {data.variants.map((v) => (
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



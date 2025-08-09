import type { AnalyzeResult } from '@/lib/types'

interface Props { data: AnalyzeResult | null }

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value || '—'}</div>
    </div>
  )
}

export default function KpiCards({ data }: Props) {
  const totalVariants = data?.variants.length ?? 0
  const uniqueSellerNames = new Set<string>()
  if (data?.variants) {
    for (const v of data.variants) for (const s of v.sellers) uniqueSellerNames.add(s.name)
  }
  const totalSellers = uniqueSellerNames.size

  // fastest delivery (min date)
  let fastest = '—'
  if (data?.variants) {
    const dates = data.variants.flatMap((v) => v.sellers.map((s) => s.deliveryDate)).filter(Boolean)
    if (dates.length) {
      fastest = dates.sort()[0]
    }
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Kpi label="Product Name" value={data?.productName || '—'} />
      <Kpi label="Total Variants" value={String(totalVariants)} />
      <Kpi label="Total Sellers" value={String(totalSellers)} />
      <Kpi label="Fastest Delivery" value={fastest} />
      <Kpi label="Attractiveness" value={typeof data?.analytics?.attractivenessIndex === 'number' ? String(data.analytics.attractivenessIndex) : '—'} />
    </div>
  )
}


